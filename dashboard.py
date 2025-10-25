import streamlit as st
import pandas as pd
import plotly.express as px
import json
from datetime import date

# Set the page configuration for a wider layout
st.set_page_config(
    layout="wide", 
    page_title="UDYAM Enterprise Dashboard", 
    initial_sidebar_state="collapsed" # Ensure no sidebar is visible
)

# Input file (Updated to the Mizoram sample file)
file_name = "/Users/thesanthoshsankaran/APU MAD/D3 Storytelling Initiative/UDYAM Dashboard/udyam statewise data/udyam_maharashtra_data_20251024-182305.csv"

# --- NIC 2-Digit Section Mapping for Descriptive Labels ---
# This dictionary maps the 2-digit NIC codes to their high-level industry description
NIC_SECTION_MAPPING = {
    '01': 'Crop & Animal Production', '02': 'Forestry and Logging',
    '10': 'Manufacture of Food Products', '13': 'Manufacture of Textiles',
    '14': 'Manufacture of Wearing Apparel', '16': 'Manufacture of Wood & Cork',
    '25': 'Manufacture of Metal Products', '41': 'Construction of Buildings',
    '43': 'Specialised Construction', '45': 'Motor Vehicle Trade/Repair',
    '46': 'Wholesale Trade', '47': 'Retail Trade', 
    '49': 'Land Transport', '55': 'Accommodation', 
    '56': 'Food & Beverage Services', '62': 'IT & Computer Programming', 
    '68': 'Real Estate Activities', '73': 'Advertising & Market Research', 
    '85': 'Education', '86': 'Human Health Activities', 
    '96': 'Other Personal Service Activities',
    '00': 'Unspecified Section'
}

# --- 1. Data Loading and Preprocessing ---

@st.cache_data
def load_and_process_data(file_path):
    """
    Loads data from CSV, cleans columns, and parses the JSON in the 'Activities' column.
    Adds NIC 3-Digit Code for filtering and an Industry_Suggestion for search.
    """
    try:
        # NOTE: Using a relative file path assumption
        df = pd.read_csv(file_path) 

        # 1. Convert 'RegistrationDate' to datetime objects
        df['RegistrationDate'] = pd.to_datetime(df['RegistrationDate'], format='%d/%m/%Y', errors='coerce')

        # 2. Clean 'Pincode' to remove decimals and treat as string/integer
        df['Pincode'] = pd.to_numeric(df['Pincode'], errors='coerce').fillna(0).astype(int).astype(str)

        # 3. Parse 'Activities' JSON to extract Description and NIC Code
        def parse_activities(activities_str):
            try:
                # Cleaning the escaped quotes typical in CSV JSON fields (e.g., '""' to '"')
                cleaned_str = activities_str.replace('""', '"').replace('"[', '[').replace(']"', ']')
                data = json.loads(cleaned_str)
                # Extract primary activity details (first entry)
                description = data[0].get('Description', 'Unspecified Activity')
                nic_code = str(data[0].get('NIC5DigitId', '00000'))
                return description, nic_code
            except (json.JSONDecodeError, TypeError, IndexError):
                return 'Unspecified Activity', '00000'

        # Apply the parsing function and create new columns
        df[['ActivityDescription', 'NIC5DigitId']] = df['Activities'].apply(
            lambda x: pd.Series(parse_activities(str(x))) 
        )
        
        # 4. Create the high-level NIC Section (first two digits)
        df['NIC_Section'] = df['NIC5DigitId'].str[:2].replace('', '00')
        
        # NEW: Create descriptive NIC section column for visualization
        df['NIC_Section_Desc'] = df['NIC_Section'].map(NIC_SECTION_MAPPING).fillna('Other/Unmapped Section')
        
        # Creating a better description for bar graph
        df['NIC_Section_Code_Desc'] = df['NIC_Section'] + ' - ' + df['NIC_Section_Desc']

        # NEW: Create NIC 3-Digit Code for filtering
        df['NIC3DigitId'] = df['NIC5DigitId'].str[:3].replace('', '000')

        # 5. Clean up string fields: CommunicationAddress and EnterpriseName
        df['CommunicationAddress'] = df['CommunicationAddress'].fillna('').astype(str)
        df['EnterpriseName'] = df['EnterpriseName'].fillna('').astype(str) 
        
        # Drop rows where RegistrationDate could not be parsed
        df.dropna(subset=['RegistrationDate'], inplace=True)
        
        # --- PREPARE SUGGESTIONS FOR MULTI-SELECT FIELDS ---
        # Combined Industry Suggestions (Now based on NIC 3-Digit)
        df['Industry_Suggestion'] = df['NIC3DigitId'] + ' - ' + df['ActivityDescription']
        industry_suggestions = sorted(df['Industry_Suggestion'].unique().tolist())
        
        # Enterprise Name Suggestions
        name_suggestions = sorted(df['EnterpriseName'].unique().tolist())
        
        # Pincode Suggestions
        pincode_options = sorted(df['Pincode'].unique().tolist())
        
        # Communication Address Suggestions
        address_options = sorted(df['CommunicationAddress'].unique().tolist())
        
        return df, industry_suggestions, name_suggestions, pincode_options, address_options
    
    except FileNotFoundError:
        st.error(f"Error: The file '{file_path}' was not found. Please ensure the file is present in the same directory.")
        return pd.DataFrame(), [], [], [], []

# Load the dataframe and suggestions
df, industry_suggestions, name_suggestions, pincode_options, address_options = load_and_process_data(file_name)

if df.empty:
    st.stop()

# --- 2. Top-of-Page Filters (Multi-Select Updates) ---

st.title("📊 UDYAM Registrations Dashboard")
st.markdown("Use the filters to refine the data for **{:,}** total records.".format(df.shape[0]))

with st.expander("Filter Controls (Click to expand)", expanded=True):
    
    col_time, col_geo, col_search = st.columns(3) 
    district_filter_applied = False
    
    # --- Col A: TIME ---
    with col_time:
        st.subheader("Time")
        # 1. Date Range (remains a slider - only non-multi-select filter)
        min_date = df['RegistrationDate'].min().date()
        max_date = df['RegistrationDate'].max().date()
        date_range = st.slider(
            "1. Registration Date Range",
            min_value=min_date,
            max_value=max_date,
            value=(min_date, max_date),
            format="YYYY-MM-DD",
        )
        start_date = pd.to_datetime(date_range[0])
        end_date = pd.to_datetime(date_range[1])
        
        date_filtered_df = df[
            (df['RegistrationDate'] >= start_date) & 
            (df['RegistrationDate'] <= end_date)
        ]

    # --- Col B: GEOGRAPHY (State & District) ---
    with col_geo:
        st.subheader("Geography")
        
        # 2. State (UPDATED to Selectbox for single selection and search)
        all_states = sorted(date_filtered_df['State'].unique().tolist())
        state_options = ['All States'] + all_states
        
        selected_state = st.selectbox(
            "2. Select State", 
            options=state_options, 
            index=0, # Default to 'All States'
            help="Select or type to filter by State."
        )
        
        # Intermediate filtering based on State selection
        if selected_state == 'All States':
            state_filtered_df = date_filtered_df
        else:
            state_filtered_df = date_filtered_df[date_filtered_df['State'] == selected_state]

        # 3. District (UPDATED to Selectbox for single selection and search)
        # Options are now dependent on the selected state
        all_districts = sorted(state_filtered_df['District'].unique().tolist())
        district_options = ['All Districts'] + all_districts
        
        selected_district = st.selectbox(
            "3. Select District", 
            options=district_options,
            index=0, # Default to 'All Districts'
            help="Select or type to filter by District (filtered by State selection)."
        )

        # Final filtering for Geography
        if selected_district == 'All Districts':
            district_filtered_df = state_filtered_df
        else:
            district_filter_applied = True
            district_filtered_df = state_filtered_df[state_filtered_df['District'] == selected_district]

    # --- Col C: SEARCH (Pincode, NIC/Activity, Name, Address) ---
    with col_search:
        st.subheader("Search Parameters")
        
        # 4. Combined NIC / Activity Search (Multi-select, using 3-Digit NIC)
        selected_industry = st.multiselect(
            "5. Filter by Industry (NIC 3-Digit / Activity)", 
            options=industry_suggestions,
            default=[],
            help="Select one or more NIC 3-Digit Codes or Activities."
        )

        # 5. Enterprise Name (Multi-Select, options are dynamic)
        name_options = sorted(district_filtered_df['EnterpriseName'].unique().tolist())
        selected_enterprise_name = st.multiselect(
            "6. Filter by Enterprise Name", 
            options=name_options,
            default=[],
            help="Select one or more business names."
        )

        # 6. Pincode (Multi-Select)
        selected_pincode = st.multiselect(
            "4. Filter by Pincode", 
            options=pincode_options,
            default=[],
            help="Select one or more Pincodes."
        )

# --- 3. Final Filtering Logic (Sequential Application) ---

# Use the result of the geography filtering as the base
filtered_df = district_filtered_df.copy()

# 1. Pincode filter (Now uses .isin() for multi-select)
if selected_pincode:
    filtered_df = filtered_df[filtered_df['Pincode'].isin(selected_pincode)]

# 2. Combined NIC/Activity Filter (using NIC 3-Digit)
if selected_industry:
    # Extract the 3-digit NIC codes from the selected strings
    selected_nic3_codes = [item.split(' - ')[0].strip() for item in selected_industry]
    filtered_df = filtered_df[filtered_df['NIC3DigitId'].isin(selected_nic3_codes)]


# 3. Enterprise Name filter (Now uses .isin() for multi-select)
if selected_enterprise_name:
    filtered_df = filtered_df[filtered_df['EnterpriseName'].isin(selected_enterprise_name)]

# --- 4. Main Dashboard Layout and Visualizations ---

st.markdown("---")

if filtered_df.empty:
    st.warning("No data matches your current filter selections. Please adjust the filters above.")
else:
    # IMPORTANT FIX: Create a fresh copy to prevent potential Streamlit/Pandas 
    # internal errors related to 'PandasThen' objects
    filtered_df = filtered_df.copy() 
    
    # --- KPIs ---
    st.header("Key Performance Indicators (KPIs) - Filtered Results")
    
    # Adjusted columns: [1, 2, 1] to give the middle column (Top Industry Description) more space
    col1, col2, col3 = st.columns([1, 2, 1]) 

    # KPI 1: Total Registrations
    with col1:
        st.metric(label="Total Registrations", value=f"{filtered_df.shape[0]:,}")
    
    # KPI 2: Top Industry Description (Dynamic based on filter) - WIDER
    with col2:
        # Calculate the most frequent activity description
        top_activity_desc = filtered_df['ActivityDescription'].mode().iloc[0] if not filtered_df['ActivityDescription'].empty else "No Activity"
        st.metric(label="Top Industry Description", value=top_activity_desc)

    # KPI 3: Average Daily Registrations (Dynamic based on filter)
    with col3:
        # Group by day and calculate the mean count
        daily_reg = filtered_df.groupby(pd.Grouper(key='RegistrationDate', freq='D')).size().reset_index(name='Count')
        avg_daily = daily_reg['Count'].mean() if not daily_reg.empty else 0
        st.metric(label="Average Daily Registrations", value=f"{avg_daily:.2f}")

    st.markdown("---")

    # --- Trend and Geo Visualization ---
    st.header("Trend and Geographic Distribution")
    trend_col, nic_col = st.columns(2)

    with trend_col:
        st.subheader("Monthly Registration Trend")
        monthly_reg = filtered_df.groupby(pd.Grouper(key='RegistrationDate', freq='M')).size().reset_index(name='Registrations')
        monthly_reg['Month'] = monthly_reg['RegistrationDate'].dt.to_period('M').astype(str)

        fig_trend = px.line(
            monthly_reg, 
            x='Month', 
            y='Registrations', 
            title='Monthly Enterprise Registrations',
            markers=True
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    # --- Categorical Visualization ---
    st.header("Industry Categorization")
    
    activity_col, geo_col = st.columns(2)

    with nic_col:
        st.subheader("Top 10 NIC Sections (2-Digit Description)")
        
        # MODIFIED: Use the new descriptive column for visualization
        nic_count = filtered_df['NIC_Section_Code_Desc'].value_counts().head(10).reset_index(name='Count')
        nic_count.rename(columns={'NIC_Section_Code_Desc': 'NIC Section'}, inplace=True)
        nic_count = nic_count.copy() 

        # Plot as a vertical bar chart, similar to the district chart
        fig_nic = px.bar(
            nic_count,
            x='NIC Section', # Use the descriptive name on the X-axis
            y='Count',       # Y-axis for count
            color='Count',
            color_continuous_scale=px.colors.sequential.Agsunset, 
            title='Top 10 Distribution by NIC Section'
        )

        fig_nic.layout.update(showlegend=False)

        # Removed x-axis rotation to match District chart style
        
        st.plotly_chart(fig_nic, use_container_width=True)
        
    with activity_col:
        st.subheader("Top Specific Business Activities (Top 15)")
        
        top_activities_count = filtered_df['ActivityDescription'].value_counts().head(15).reset_index()
        top_activities_count.columns = ['Activity Description', 'Count']
        
        # Horizontal bar chart for better readability of long labels
        fig_activity = px.bar(
            # Data is sorted in ascending=True, meaning largest count is last (at the top of the plot)
            top_activities_count.sort_values(by='Count', ascending=True), 
            x='Count',
            y='Activity Description',
            orientation='h',
            color='Count',
            color_continuous_scale=px.colors.sequential.Plotly3,
            title='Ranking of Top 15 Enterprise Activities'
        )

        fig_activity.layout.update(showlegend=False)

        # REMOVED: fig_activity.update_layout(yaxis={'autorange': 'reversed'}) 
        # By removing the y-axis reversal, the largest count (last in ascending sort) now appears at the top.
        st.plotly_chart(fig_activity, use_container_width=True)

    with geo_col:
        if not district_filter_applied:
            st.subheader("Registrations by District")
            reg_by_district = filtered_df['District'].value_counts().reset_index(name='Count')
            
            # Bar chart retained
            fig_district = px.bar(
                reg_by_district,
                x='District',
                y='Count',
                color='Count',
                title='Total Registrations per District'
            )

            fig_district.layout.update(showlegend=False)

            st.plotly_chart(fig_district, use_container_width=True)

    st.markdown("---")

    # --- Filtered Data Display ---
    st.subheader("Filtered Enterprise Data Preview")
    display_cols = [
        'RegistrationDate', 
        'EnterpriseName', 
        'State', 
        'District', 
        'Pincode', 
        'NIC_Section',
        'ActivityDescription',
        'CommunicationAddress',
    ]
    st.dataframe(filtered_df[display_cols], height=300, use_container_width=True)
