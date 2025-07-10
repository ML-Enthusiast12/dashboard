import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
from dateutil import parser
import json

# Streamlit page configuration
st.set_page_config(page_title="Dashboard", layout="wide")

# Hardcoded Monday.com API setup
API_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjUzNjcxMTM2NCwiYWFpIjoxMSwidWlkIjo3ODEyNjAzOSwiaWFkIjoiMjAyNS0wNy0wOVQwNjoxMjoxMi4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6Mjg1MTUzNDksInJnbiI6InVzZTEifQ.7xlG-veqLRWWL5RqmmJ5Ve4dxVlhnv0Z43CGktBnmp8"
BOARD_ID = "9148781915"
API_URL = "https://api.monday.com/v2"

# Configuration for second dashboard
API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjUzNjcxMTM2NCwiYWFpIjoxMSwidWlkIjo3ODEyNjAzOSwiaWFkIjoiMjAyNS0wNy0wOVQwNjoxMjoxMi4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6Mjg1MTUzNDksInJnbiI6InVzZTEifQ.7xlG-veqLRWWL5RqmmJ5Ve4dxVlhnv0Z43CGktBnmp8"
STATUS_COLUMN_ID = "color_mkqyyxxc"
DUE_DATE_COLUMN_ID = "date_mkqyf70p"
CREATE_DATE_COLUMN_ID = "date_mkqyvac7"
DONE_STATUSES = ["Done"]

# Headers for API requests
headers = {
    "Authorization": "Bearer " + API_TOKEN,
    "Content-Type": "application/json"
}

# Function to fetch data from Monday.com with pagination (First Dashboard)
@st.cache_data
def fetch_monday_data():
    if not API_TOKEN or not BOARD_ID or BOARD_ID == "YOUR_BOARD_ID_HERE":
        st.error("Please update the hardcoded API token and Board ID in the code with valid values.")
        return [], None
    
    all_items = []
    cursor = None
    
    while True:
        query = """
        query ($boardId: [ID!]!, $cursor: String) {
            boards(ids: $boardId) {
                id
                name
                columns {
                    id
                    title
                }
                items_page(limit: 500, cursor: $cursor) {
                    cursor
                    items {
                        id
                        name
                        created_at
                        column_values {
                            id
                            value
                        }
                    }
                }
            }
        }
        """
        
        variables = {"boardId": [BOARD_ID], "cursor": cursor}
        
        try:
            response = requests.post(API_URL, json={'query': query, 'variables': variables}, headers=headers)
            response.raise_for_status()
            data = response.json()
            if 'errors' in data:
                st.error(f"Monday.com API errors: {data['errors']}")
                return [], None
            board_data = data['data']['boards'][0] if data['data']['boards'] else None
            if not board_data:
                break
            
            items_page = board_data['items_page']
            all_items.extend(items_page['items'])
            cursor = items_page['cursor']
            
            if not cursor:
                break
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching data from Monday.com: {str(e)}")
            if hasattr(response, 'text') and response.text:
                st.error(f"Response details: {response.text}")
            return [], None
    
    return all_items, board_data['columns'] if board_data else None

# Function to process Monday.com data (First Dashboard)
def process_data(items, columns):
    tasks = []
    column_map = {col['title']: col['id'] for col in columns}
    status_id = column_map.get("Status")
    create_date_id = column_map.get("Create Date")
    due_date_id = column_map.get("Due Date")
    
    if not status_id:
        st.warning("Could not find 'Status' column. Please check your board configuration.")
        return pd.DataFrame()
    if not create_date_id:
        st.warning("Could not find 'Create Date' column. Please check your board configuration.")
        return pd.DataFrame()
    if not due_date_id:
        st.warning("Could not find 'Due Date' column. Please check your board configuration.")
        return pd.DataFrame()
    
    for item in items:
        task = {
            'name': item['name'],
            'created_at': None,
            'status': None,
            'due_date': None
        }
        
        for column in item['column_values']:
            if column['id'] == status_id:
                if column['value']:
                    try:
                        status_data = json.loads(column['value'])
                        index_value = status_data.get('index')
                        if index_value is not None:
                            if isinstance(index_value, (int, str)):
                                status_map = {0: 'Done', 1: 'Outstanding', 2: 'Overdue'}
                                task['status'] = status_map.get(int(index_value), 'Overdue')
                            else:
                                task['status'] = str(index_value)
                        else:
                            task['status'] = status_data.get('label', status_data.get('text', 'Overdue'))
                    except json.JSONDecodeError:
                        task['status'] = 'Overdue'
            if column['id'] == create_date_id:
                if column['value']:
                    try:
                        date_data = json.loads(column['value'])
                        task['created_at'] = parser.parse(date_data.get('date', '')).date() if isinstance(date_data, dict) else parser.parse(column['value'].strip('"')).date()
                    except (json.JSONDecodeError, ValueError):
                        task['created_at'] = parser.parse(column['value'].strip('"')).date() if column['value'] else None
                else:
                    task['created_at'] = parser.parse(item['created_at']).date()
            if column['id'] == due_date_id:
                if column['value']:
                    try:
                        date_data = json.loads(column['value'])
                        task['due_date'] = parser.parse(date_data.get('date', '')).date() if isinstance(date_data, dict) else parser.parse(column['value'].strip('"')).date()
                    except (json.JSONDecodeError, ValueError):
                        task['due_date'] = parser.parse(column['value'].strip('"')).date() if column['value'] else None
        
        if task['created_at'] is None:
            task['created_at'] = parser.parse(item['created_at']).date()
        
        tasks.append(task)
    
    return pd.DataFrame(tasks)

# Function to prepare data for visualization (First Dashboard)
def prepare_chart_data(df, start_date, end_date, filter_type, selected_values):
    # Ensure created_at is in Timestamp format
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    # Filter by date range
    df = df[(df['created_at'] >= pd.Timestamp(start_date)) & (df['created_at'] <= pd.Timestamp(end_date))]
    
    if filter_type == "Week":
        weeks = pd.date_range(start=start_date, end=end_date, freq='W-MON')
        week_labels = [w.strftime('%Y-%m-%d') for w in weeks]
        # Filter tasks for selected weeks using Timestamp comparisons
        filtered_df = df[df['created_at'].apply(lambda x: any(
            x >= pd.Timestamp(w) and x <= pd.Timestamp(w) + timedelta(days=6) 
            for w in weeks if w.strftime('%Y-%m-%d') in selected_values
        ))]
    else:  # Month
        months = pd.date_range(start=start_date, end=end_date, freq='MS').strftime('%Y-%m').tolist()
        filtered_df = df[df['created_at'].dt.strftime('%Y-%m').isin(selected_values)] if selected_values != ["All"] else df
    
    # Initialize data structures
    outstanding = []
    done = []
    overdue = []
    net_outstanding = []
    
    if filter_type == "Week":
        for week in weeks:
            week_end = pd.Timestamp(week) + timedelta(days=6)
            week_tasks = filtered_df[(filtered_df['created_at'] >= pd.Timestamp(week)) & (filtered_df['created_at'] <= week_end)]
            week_outstanding = len(week_tasks[week_tasks['status'].isin(['Outstanding', 'Overdue'])])
            week_done = len(week_tasks[week_tasks['status'] == 'Done'])
            week_overdue = len(week_tasks[week_tasks['status'] == 'Overdue'])
            outstanding.append(week_outstanding)
            done.append(week_done)
            overdue.append(week_overdue)
            net_outstanding.append(week_outstanding - week_done)
    else:  # Month
        for month in selected_values if selected_values != ["All"] else months:
            month_df = filtered_df[filtered_df['created_at'].dt.strftime('%Y-%m') == month]
            month_outstanding = len(month_df[month_df['status'].isin(['Outstanding', 'Overdue'])])
            month_done = len(month_df[month_df['status'] == 'Done'])
            month_overdue = len(month_df[month_df['status'] == 'Overdue'])
            outstanding.append(month_outstanding)
            done.append(month_done)
            overdue.append(month_overdue)
            net_outstanding.append(month_outstanding - month_done)
        week_labels = selected_values if selected_values != ["All"] else months
    
    return week_labels, outstanding, done, overdue, net_outstanding

# Second Dashboard Functions
def fetch_monday_data_second():
    all_items = []
    cursor = None
    while True:
        cursor_part = f', cursor: "{cursor}"' if cursor else ""
        query = f"""
        {{
          boards(ids: [{BOARD_ID}]) {{
            items_page(limit: 100{cursor_part}) {{
              cursor
              items {{
                name
                column_values(ids: ["{STATUS_COLUMN_ID}", "{DUE_DATE_COLUMN_ID}", "{CREATE_DATE_COLUMN_ID}"]) {{
                  id
                  text
                }}
              }}
            }}
          }}
        }}
        """
        headers = {"Authorization": API_KEY}
        response = requests.post("https://api.monday.com/v2", json={"query": query}, headers=headers, timeout=30)
        if response.status_code != 200:
            st.error(f"❌ API request failed: {response.status_code}")
            st.write("Debug: API response:", response.text)
            return {}
        json_data = response.json()
        if "errors" in json_data:
            st.error("❌ Monday API errors:")
            st.json(json_data["errors"])
            return {}
        items = json_data["data"]["boards"][0]["items_page"]["items"]
        all_items.extend(items)
        cursor = json_data["data"]["boards"][0]["items_page"].get("cursor")
        if not cursor:
            break
    return {"data": {"boards": [{"items_page": {"items": all_items}}]}}

def process_data_second(raw_data):
    if "data" not in raw_data or not raw_data["data"]["boards"][0]["items_page"]["items"]:
        st.warning("⚠️ No valid data found.")
        return pd.DataFrame()
    tasks = []
    for item in raw_data["data"]["boards"][0]["items_page"]["items"]:
        task = {"name": item.get("name", "Unknown"), "create_date": None, "status": None, "due_date": None}
        for col in item.get("column_values", []):
            if col.get("id") == STATUS_COLUMN_ID:
                task["status"] = col.get("text", "Unknown")
            elif col.get("id") == DUE_DATE_COLUMN_ID:
                task["due_date"] = col.get("text", "")
            elif col.get("id") == CREATE_DATE_COLUMN_ID:
                task["create_date"] = col.get("text", "")
        tasks.append(task)
    df = pd.DataFrame(tasks)
    df["create_date"] = pd.to_datetime(df["create_date"], errors="coerce", utc=True)
    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce", utc=True)
    return df

def calculate_metrics(df):
    today = pd.Timestamp(datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0), tz='UTC')
    past_30_days = today - timedelta(days=30)
    past_15_days = today - timedelta(days=15)
    df = df[df["create_date"] >= past_30_days]
    df_current = df[df["create_date"] >= past_15_days]
    df_prev = df[(df["create_date"] < past_15_days) & (df["create_date"] >= past_30_days)]

    current_velocity = df_current[df_current["status"].isin(DONE_STATUSES)].shape[0]
    prev_velocity = df_prev[df_prev["status"].isin(DONE_STATUSES)].shape[0]
    velocity_delta = calc_delta(prev_velocity, current_velocity)

    overdue_current = df_current[(df_current["due_date"] < today) & (~df_current["status"].isin(DONE_STATUSES))].shape[0]
    overdue_prev = df_prev[(df_prev["due_date"] < past_15_days) & (~df_prev["status"].isin(DONE_STATUSES))].shape[0]
    overdue_delta = calc_delta(overdue_prev, overdue_current)

    st.write(f"Debug: Current Velocity={current_velocity}, Prev Velocity={prev_velocity}")
    st.write(f"Debug: Current Overdue={overdue_current}, Prev Overdue={overdue_prev}")

    return current_velocity, velocity_delta, overdue_current, overdue_delta, overdue_prev

def calc_delta(previous, current):
    if previous == 0:
        return 100 if current > 0 else 0
    return round(((current - previous) / previous) * 100, 2)

# Main dashboard function
def actions_by_week_dashboard():
    st.header("Actions By Week Dashboard")
    
    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.now() - timedelta(weeks=8), key="start_date_1")
    with col2:
        end_date = st.date_input("End Date", value=datetime.now(), key="end_date_1")
    
    # Filter type selection
    filter_type = st.radio("Filter by:", ["Week", "Month"], key="filter_type_1")
    
    # Fetch and process data
    items, columns = fetch_monday_data()
    if items and columns:
        df = process_data(items, columns)
        
        if not df.empty:
            # Prepare filter options
            if filter_type == "Week":
                weeks = pd.date_range(start=start_date, end=end_date, freq='W-MON')
                week_options = [w.strftime('%Y-%m-%d') for w in weeks]
                selected_weeks = st.multiselect("Select Weeks:", week_options, default=week_options, key="weeks_1")
            else:  # Month
                months = pd.date_range(start=start_date, end=end_date, freq='MS').strftime('%Y-%m').tolist()
                selected_months = st.multiselect("Select Months:", ["All"] + months, default=["All"], key="months_1")
            
            # Prepare chart data
            week_labels, outstanding, done, overdue, net_outstanding = prepare_chart_data(df, start_date, end_date, filter_type, selected_weeks if filter_type == "Week" else selected_months)
            
            # Create stacked bar chart with lines
            fig = go.Figure()
            
            # Stacked bars
            fig.add_trace(go.Bar(
                x=week_labels,
                y=outstanding,
                name="Outstanding",
                marker_color='orange'
            ))
            fig.add_trace(go.Bar(
                x=week_labels,
                y=done,
                name="Done",
                marker_color='green'
            ))
            
            # Line A: Net Outstanding
            fig.add_trace(go.Scatter(
                x=week_labels,
                y=net_outstanding,
                name="Net Outstanding",
                line=dict(color='blue', width=2)
            ))
            
            # Line B: Overdue
            fig.add_trace(go.Scatter(
                x=week_labels,
                y=overdue,
                name="Overdue",
                line=dict(color='red', width=2)
            ))
            
            # Update layout
            fig.update_layout(
                title="Actions By Week/Month",
                xaxis_title="Week/Month Starting",
                yaxis_title="Number of Tasks",
                barmode='stack',
                template='plotly_white',
                height=600
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No valid task data processed. Check column names or data.")
    else:
        st.warning("No data retrieved from Monday.com. Please check the hardcoded API token, Board ID, or column configuration.")

def team_performance_dashboard():
    st.header("📊 Team Performance Dashboard (Last 30 Days)")
    st.markdown("""
    **Color Coding:**
    - **Velocity**: Green if % change is positive (more tasks completed), Red if negative.
    - **Overdue**: Red if overdue increased, Green if overdue decreased or no change.
    """)
    with st.spinner("Fetching data from Monday.com..."):
        raw_data = fetch_monday_data_second()
        df = process_data_second(raw_data)
        if df.empty:
            st.warning("No data to show.")
            return
        v_now, v_delta, o_now, o_delta, o_prev = calculate_metrics(df)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            """
            <div style="border: 2px solid black; padding: 10px;">
                <h3 style="text-align: center;">✅ Velocity (Completed Tasks)</h3>
                <p style="text-align: center; font-size: 24px;">{}</p>
                <p style="text-align: center; font-size: 18px; color: {};">{}%</p>
            </div>
            """.format(v_now, "green" if v_delta >= 0 else "red", v_delta),
            unsafe_allow_html=True
        )
    with col2:
        # Correct overdue coloring logic:
        if o_now > o_prev:
            overdue_color = "red"
        else:
            overdue_color = "green"
        st.markdown(
            """
            <div style="border: 2px solid black; padding: 10px;">
                <h3 style="text-align: center;">❌ Overdue Tasks</h3>
                <p style="text-align: center; font-size: 24px;">{}</p>
                <p style="text-align: center; font-size: 18px; color: {};">{}%</p>
            </div>
            """.format(o_now, overdue_color, o_delta),
            unsafe_allow_html=True
        )
    with st.expander("📋 Task Data"):
        st.dataframe(df)

# Main function
def main():
    st.title("Combined Dashboard")
    
    # Create tabs for both dashboards
    tab1, tab2 = st.tabs(["Actions By Week", "Team Performance"])
    
    with tab1:
        actions_by_week_dashboard()
    
    with tab2:
        team_performance_dashboard()

if __name__ == "__main__":
    main()