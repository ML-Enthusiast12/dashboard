
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import requests
from dateutil import parser
import json
import os

# Streamlit page configuration
st.set_page_config(page_title="Combined Monday.com Dashboard", layout="wide")

# Monday.com API setup
API_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjUzNjcxMTM2NCwiYWFpIjoxMSwidWlkIjo3ODEyNjAzOSwiaWFkIjoiMjAyNS0wNy0wOVQwNjoxMjoxMi4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6Mjg1MTUzNDksInJnbiI6InVzZTEifQ.7xlG-veqLRWWL5RqmmJ5Ve4dxVlhnv0Z43CGktBnmp8"
API_URL = "https://api.monday.com/v2"

# Board IDs and column mappings for Outstanding Tasks Dashboard
BOARD_IDS = {"project1": "9148781915", "Project2": "9567843297"}
COLUMN_MAPPINGS = {
    "9148781915": {
        "due_date": "date_mkqyf70p",
        "status": "color_mkqyyxxc",
        "person": "dropdown_mkqyqkcq",
        "person_alt": "text_mkqyc3mv",
        "create_date": "date_mkqyvac7"
    },
    "9567843297": {
        "due_date": "date_mksr2mw0",
        "status": "color_mksrzkw5",
        "person": "text_mksrzkw5",
        "person_alt": "text_mksrys4",
        "create_date": "date_mksrsv4t"
    }
}

# Constants for Team Performance Dashboard
STATUS_COLUMN_ID = "color_mkqyyxxc"
DUE_DATE_COLUMN_ID = "date_mkqyf70p"
CREATE_DATE_COLUMN_ID = "date_mkqyvac7"
DONE_STATUSES = ["Done"]

# Headers for API requests
headers = {
    "Authorization": API_TOKEN,
    "Content-Type": "application/json"
}

# Get current week for Outstanding Tasks Dashboard
today = datetime.now()
start_of_week = today - timedelta(days=today.weekday())
end_of_week = start_of_week + timedelta(days=6)

# --- Actions By Week Dashboard Functions ---
@st.cache_data
def fetch_monday_data_actions():
    BOARD_ID = "9148781915"
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
            return [], None
    return all_items, board_data['columns'] if board_data else None

def process_data_actions(items, columns):
    tasks = []
    column_map = {col['title']: col['id'] for col in columns}
    status_id = column_map.get("Status")
    create_date_id = column_map.get("Create Date")
    due_date_id = column_map.get("Due Date")
    if not status_id or not create_date_id or not due_date_id:
        st.warning("Required columns not found. Check board configuration.")
        return pd.DataFrame()
    for item in items:
        task = {'name': item['name'], 'created_at': None, 'status': None, 'due_date': None}
        for column in item['column_values']:
            if column['id'] == status_id:
                if column['value']:
                    try:
                        status_data = json.loads(column['value'])
                        index_value = status_data.get('index')
                        if index_value is not None:
                            status_map = {0: 'Done', 1: 'Outstanding', 2: 'Overdue'}
                            task['status'] = status_map.get(int(index_value), 'Overdue')
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

def prepare_chart_data_actions(df, start_date, end_date, filter_type, selected_values):
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df[(df['created_at'] >= pd.Timestamp(start_date)) & (df['created_at'] <= pd.Timestamp(end_date))]
    if filter_type == "Week":
        weeks = pd.date_range(start=start_date, end=end_date, freq='W-MON')
        week_labels = [w.strftime('%Y-%m-%d') for w in weeks]
        filtered_df = df[df['created_at'].apply(lambda x: any(
            x >= pd.Timestamp(w) and x <= pd.Timestamp(w) + timedelta(days=6) 
            for w in weeks if w.strftime('%Y-%m-%d') in selected_values
        ))]
    else:
        months = pd.date_range(start=start_date, end=end_date, freq='MS').strftime('%Y-%m').tolist()
        filtered_df = df[df['created_at'].dt.strftime('%Y-%m').isin(selected_values)] if selected_values != ["All"] else df
    outstanding, done, overdue, net_outstanding = [], [], [], []
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
    else:
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

def actions_by_week_dashboard():
    st.header("Actions By Week - Super Chart")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.now() - timedelta(weeks=8), key="start_date_1")
    with col2:
        end_date = st.date_input("End Date", value=datetime.now(), key="end_date_1")
    filter_type = st.radio("Filter by:", ["Week", "Month"], key="filter_type_1")
    items, columns = fetch_monday_data_actions()
    if items and columns:
        df = process_data_actions(items, columns)
        if not df.empty:
            if filter_type == "Week":
                weeks = pd.date_range(start=start_date, end=end_date, freq='W-MON')
                week_options = [w.strftime('%Y-%m-%d') for w in weeks]
                selected_weeks = st.multiselect("Select Weeks:", week_options, default=week_options, key="weeks_1")
            else:
                months = pd.date_range(start=start_date, end=end_date, freq='MS').strftime('%Y-%m').tolist()
                selected_months = st.multiselect("Select Months:", ["All"] + months, default=["All"], key="months_1")
            week_labels, outstanding, done, overdue, net_outstanding = prepare_chart_data_actions(df, start_date, end_date, filter_type, selected_weeks if filter_type == "Week" else selected_months)
            fig = go.Figure()
            fig.add_trace(go.Bar(x=week_labels, y=outstanding, name="Outstanding", marker_color='orange'))
            fig.add_trace(go.Bar(x=week_labels, y=done, name="Done", marker_color='green'))
            fig.add_trace(go.Scatter(x=week_labels, y=net_outstanding, name="Net Outstanding", line=dict(color='blue', width=2)))
            fig.add_trace(go.Scatter(x=week_labels, y=overdue, name="Overdue", line=dict(color='red', width=2)))
            fig.update_layout(title="Actions By Week/Month", xaxis_title="Week/Month Starting", yaxis_title="Number of Tasks", barmode='stack', template='plotly_white', height=600)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No valid task data processed. Check column names or data.")
    else:
        st.warning("No data retrieved from Monday.com. Check API token or board configuration.")
    st.divider()

# --- Team Performance Dashboard Functions ---
def fetch_monday_data_team():
    BOARD_ID = "9148781915"
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
        response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=30)
        if response.status_code != 200:
            st.error(f"❌ API request failed: {response.status_code}")
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

def process_data_team(raw_data):
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

def calculate_metrics_team(df):
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
    return current_velocity, velocity_delta, overdue_current, overdue_delta, overdue_prev

def calc_delta(previous, current):
    if previous == 0:
        return 100 if current > 0 else 0
    return round(((current - previous) / previous) * 100, 2)

def team_performance_dashboard():
    st.header("📊 Performance Indicator")
    st.markdown("""
    **Color Coding:**
    - **Velocity**: Green if % change is positive (more tasks completed), Red if negative.
    - **Overdue**: Red if overdue increased, Green if overdue decreased or no change.
    """)
    with st.spinner("Fetching data from Monday.com..."):
        raw_data = fetch_monday_data_team()
        df = process_data_team(raw_data)
        if df.empty:
            st.warning("No data to show.")
            return
        v_now, v_delta, o_now, o_delta, o_prev = calculate_metrics_team(df)
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
        overdue_color = "red" if o_now > o_prev else "green"
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
    st.divider()

# --- Outstanding Tasks Dashboard Functions ---
def get_monday_data_outstanding(board_id):
    query = """
    query {
      boards(ids: [%s]) {
        id
        name
        columns {
          id
          title
          type
        }
        items_page {
          items {
            id
            name
            column_values {
              id
              text
              value
              type
            }
            creator {
              id
              name
            }
          }
        }
      }
    }
    """ % board_id
    response = requests.post(API_URL, json={"query": query}, headers=headers)
    if response.status_code != 200:
        st.error(f"Failed to connect to Monday.com API for board {board_id}: {response.text}")
        return None
    result = response.json()
    if "errors" in result:
        st.error(f"GraphQL errors for board {board_id}: {result['errors']}")
        return None
    return result

def process_outstanding_data(filter_by_week=False, debug_mode=False, include_no_due_date=False):
    data = []
    today = datetime.now().date()
    for project, board_id in BOARD_IDS.items():
        result = get_monday_data_outstanding(board_id)
        if result is None or "data" not in result or "boards" not in result["data"] or not result["data"]["boards"]:
            if debug_mode:
                st.write(f"**Debug: API Response for {project} (Board ID: {board_id})**")
                st.json(result)
            st.warning(f"No data found for {project} (Board ID: {board_id})")
            continue
        board_columns = COLUMN_MAPPINGS.get(board_id, {})
        for board in result["data"]["boards"]:
            if not board or "items_page" not in board or "items" not in board["items_page"]:
                if debug_mode:
                    st.write(f"**Debug: No items found in board {project} (ID: {board_id})**")
                continue
            columns = {col["id"]: {"title": col["title"], "type": col["type"]} for col in board.get("columns", [])}
            if debug_mode:
                st.write(f"**Board: {project} (ID: {board_id})**")
                st.write("Available Columns:")
                for col_id, col_info in columns.items():
                    st.write(f"  - {col_id}: {col_info['title']} ({col_info['type']})")
                st.write("Board Column Mappings:")
                for mapping_key, mapping_value in board_columns.items():
                    col_title = columns.get(mapping_value, {}).get("title", "NOT FOUND")
                    st.write(f"  - {mapping_key}: {mapping_value} -> {col_title}")
                st.write("---")
            for item in board["items_page"]["items"]:
                if not item:
                    continue
                due_date = None
                status = None
                person = None
                create_date = None
                if debug_mode:
                    st.write(f"**Item: {item['name']}**")
                    st.write("Column Values:")
                    for col in item["column_values"]:
                        col_title = columns.get(col["id"], {}).get("title", "Unknown")
                        st.write(f"  - {col['id']} ({col_title}): Text='{col['text']}', Value='{col.get('value', 'N/A')}'")
                for col in item["column_values"]:
                    if col["id"] == board_columns.get("due_date") and col["text"]:
                        due_date = col["text"]
                    elif col["id"] == board_columns.get("status") and col["text"]:
                        status = col["text"]
                    elif col["id"] == board_columns.get("person") and col["text"]:
                        person = col["text"]
                    elif col["id"] == board_columns.get("person_alt") and col["text"]:
                        if not person:
                            person = col["text"]
                    elif col["id"] == board_columns.get("create_date") and col["text"]:
                        create_date = col["text"]
                if not person or not status:
                    for col in item["column_values"]:
                        if col["text"]:
                            col_title = columns.get(col["id"], {}).get("title", "").lower()
                            if not person and ("person" in col_title or "assigned" in col_title or "owner" in col_title):
                                person = col["text"]
                            if not status and ("status" in col_title or "state" in col_title):
                                status = col["text"]
                if not person:
                    person = item["creator"]["name"] if item["creator"] else "Unknown"
                if not status:
                    status = "Outstanding"
                item_name = item["name"]
                due_date_obj = None
                if due_date:
                    try:
                        date_part = due_date.split('T')[0] if 'T' in due_date else due_date
                        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y"]:
                            try:
                                due_date_obj = datetime.strptime(date_part, fmt).date()
                                break
                            except ValueError:
                                continue
                        else:
                            raise ValueError("No matching date format")
                    except ValueError as e:
                        if debug_mode:
                            st.write(f"Date parsing error for {item_name} (Board: {project}): {due_date} - {e}")
                        continue
                if filter_by_week:
                    if due_date_obj:
                        if not (start_of_week.date() <= due_date_obj <= end_of_week.date()):
                            if debug_mode:
                                st.write(f"Skipping {item_name} (Board: {project}): Due Date={due_date}, Parsed={due_date_obj}")
                            continue
                    elif not include_no_due_date:
                        if debug_mode:
                            st.write(f"Skipping {item_name} (Board: {project}): No due date")
                        continue
                if due_date_obj and due_date_obj < today and status.lower() not in ["done", "complete", "completed"]:
                    final_status = "Overdue"
                elif status.lower() in ["done", "complete", "completed"]:
                    final_status = "Done"
                else:
                    final_status = status
                if final_status.lower() not in ["done", "complete", "completed"]:
                    data.append({
                        "Project": project,
                        "Item": item_name,
                        "Person": person,
                        "Create Date": create_date,
                        "Due Date": due_date_obj,
                        "Status": final_status,
                        "Board ID": board_id
                    })
    df = pd.DataFrame(data)
    if debug_mode:
        st.write(f"**Debug: {'Weekly' if filter_by_week else 'All'} Tasks Summary**")
        st.write(f"Total tasks after filtering: {len(df)}")
        if not df.empty:
            st.write("Tasks included:")
            st.dataframe(df[["Project", "Item", "Due Date", "Status", "Person"]])
        else:
            st.write("No tasks found.")
    return df

def create_outstanding_tasks_chart(df):
    if df.empty:
        st.warning("No outstanding tasks found")
        return None
    task_counts = df.groupby(["Person", "Status"]).size().reset_index(name="Count")
    status_colors = {
        "Outstanding": "#FF8800",
        "Overdue": "#FF4444",
        "Working on it": "#007CFF",
        "Stuck": "#FF6B6B",
        "In Progress": "#4ECDC4",
        "To Do": "#FFA500",
        "Pending": "#9400D3"
    }
    fig = px.bar(
        task_counts,
        x="Count",
        y="Person",
        color="Status",
        orientation="h",
        title="Outstanding Tasks by Person",
        color_discrete_map=status_colors,
        text="Count",
        height=max(400, len(task_counts["Person"].unique()) * 60)
    )
    fig.update_traces(textposition='outside')
    fig.update_layout(
        xaxis_title="Number of Tasks",
        yaxis_title="Person",
        yaxis={'categoryorder': 'total ascending'},
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def outstanding_tasks_dashboard():
    st.header("📊 Outstanding Tasks - Due This Week Chart")
    st.markdown("**Excludes:** 'Done' status tasks | **Shows:** Correct counts for each person | **Color-coded:** By status")
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        chart_type = st.selectbox("Select Chart Type", ["All Outstanding Tasks", "Due This Week Only"], key="outstanding_chart_type")
    with col2:
        project = st.selectbox("Filter by Project", ["All"] + list(BOARD_IDS.keys()), key="outstanding_project")
    with col3:
        include_no_due_date = st.checkbox("Include Tasks Without Due Dates", False, help="Show tasks with no due date in the weekly view", key="outstanding_no_due_date")
    debug_mode = st.checkbox("Debug Mode", False, help="Shows column structure and raw data", key="outstanding_debug")
    filter_by_week = (chart_type == "Due This Week Only")
    if filter_by_week:
        st.markdown(f"**Current Week:** {start_of_week.strftime('%B %d')} - {end_of_week.strftime('%B %d, %Y')}")
        st.markdown("**Description:** Chart showing tasks due in current week by person")
    else:
        st.markdown("**Description:** Horizontal bar chart showing all non-completed tasks by person")
    with st.spinner("Fetching data from Monday.com..."):
        df = process_outstanding_data(filter_by_week=filter_by_week, debug_mode=debug_mode, include_no_due_date=include_no_due_date)
    if df is not None and not df.empty:
        if project != "All":
            df = df[df["Project"] == project]
        if df.empty:
            if filter_by_week:
                st.warning(f"No tasks due this week for {project}")
            else:
                st.warning(f"No outstanding tasks found for {project}")
            return
        st.subheader("📊 Data Summary")
        project_breakdown = df.groupby("Project").size().reset_index(name="Count")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Tasks by Project:**")
            for _, row in project_breakdown.iterrows():
                st.write(f"- {row['Project']}: {row['Count']} tasks")
        with col2:
            st.write("**Unique Statuses Found:**")
            unique_statuses = df["Status"].unique()
            for status in sorted(unique_statuses):
                count = len(df[df["Status"] == status])
                st.write(f"- {status}: {count} tasks")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if filter_by_week:
                st.metric("Tasks Due This Week", len(df))
            else:
                st.metric("Total Outstanding", len(df))
        with col2:
            st.metric("Overdue", len(df[df["Status"] == "Overdue"]))
        with col3:
            st.metric("Outstanding", len(df[df["Status"] == "Outstanding"]))
        with col4:
            st.metric("People", df["Person"].nunique())
        st.subheader("📈 Tasks by Person")
        chart_fig = create_outstanding_tasks_chart(df)
        if chart_fig:
            st.plotly_chart(chart_fig, use_container_width=True)
        st.subheader("📋 Task Counts by Person and Status")
        task_summary = df.groupby(["Person", "Status"]).size().unstack(fill_value=0)
        if not task_summary.empty:
            st.dataframe(task_summary, use_container_width=True)
        with st.expander("📝 Detailed Task List"):
            df_sorted = df.sort_values(["Person", "Status", "Due Date"], na_position='last')
            for index, row in df_sorted.iterrows():
                col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                with col1:
                    st.write(f"**{row['Item']}**")
                    st.caption(f"Project: {row['Project']}")
                with col2:
                    st.write(f"👤 {row['Person']}")
                with col3:
                    if row['Due Date']:
                        st.write(f"⏰ Due: {row['Due Date']}")
                        if filter_by_week and row['Due Date'] and start_of_week.date() <= row['Due Date'] <= end_of_week.date():
                            st.caption("📅 This Week")
                    else:
                        st.write("⏰ Due: Not set")
                with col4:
                    status = row['Status']
                    if status == "Overdue":
                        st.markdown(f"🔴 **{status}**")
                    elif status == "Outstanding":
                        st.markdown(f"🟠 **{status}**")
                    else:
                        st.markdown(f"🔵 **{status}**")
                st.divider()
        export_filename = f"outstanding_tasks_{'week' if filter_by_week else 'all'}_{datetime.now().strftime('%Y%m%d')}.csv"
        if st.button("📥 Export Tasks", key="export_outstanding"):
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=export_filename,
                mime="text/csv",
                key="download_outstanding"
            )
    else:
        st.error("❌ No outstanding tasks found or failed to fetch data from Monday.com")
        st.info("💡 Try enabling Debug Mode to see the column structure")
        st.subheader("🔍 Board Information")
        for project, board_id in BOARD_IDS.items():
            st.write(f"**{project}:** Board ID `{board_id}`")
        st.subheader("📋 Column Mappings")
        for board_id, mappings in COLUMN_MAPPINGS.items():
            project_name = [name for name, bid in BOARD_IDS.items() if bid == board_id][0]
            st.write(f"**{project_name} ({board_id}):**")
            for key, value in mappings.items():
                st.write(f"  - {key}: {value}")
    st.divider()

# --- Simple Outstanding Tasks Dashboard Functions (from provided code) ---
def fetch_monday_data_simple():
    BOARD_ID = "9148781915"
    query = """
    query {
      boards(ids: %s) {
        name
        items_page {
          items {
            name
            column_values(ids: ["color_mkqyyxxc", "dropdown_mkqyqkcq", "date_mkqyf70p", "text_mkqyjgqr"]) {
              id
              text
            }
          }
        }
      }
    }
    """ % BOARD_ID
    response = requests.post(API_URL, json={"query": query}, headers=headers)
    if response.status_code != 200:
        st.error(f"API request failed with status {response.status_code}: {response.text}")
        return None
    data = response.json()
    if "data" not in data or "boards" not in data["data"] or not data["data"]["boards"]:
        st.error("No data found in API response")
        return None
    return data

def process_data_simple(data):
    records = []
    for board in data["data"]["boards"]:
        items_page = board.get("items_page", {})
        if isinstance(items_page, dict) and "items" in items_page:
            for item in items_page["items"]:
                row = {"Item": item.get("name", "")}
                for col in item.get("column_values", []):
                    if col.get("id") == "color_mkqyyxxc":
                        row["Status"] = col.get("text", "")
                    elif col.get("id") == "dropdown_mkqyqkcq":
                        row["Person"] = col.get("text", "")
                    elif col.get("id") == "date_mkqyf70p":
                        row["Due Date"] = col.get("text", "")
                    elif col.get("id") == "text_mkqyjgqr":
                        row["Description"] = col.get("text", "")
                records.append(row)
    return pd.DataFrame(records)

def simple_outstanding_tasks_dashboard():
    st.header("Outstanding Tasks - All Charts ")
    data = fetch_monday_data_simple()
    if data is None:
        return
    df = process_data_simple(data)
    st.subheader("Raw Monday.com Data")
    st.write(df)
    if "Status" not in df.columns:
        st.error("Column 'Status' not found in data. Available columns: " + ", ".join(df.columns))
        return
    df_outstanding = df[df["Status"].isin(["Overdue", "Outstanding"])]
    if df_outstanding.empty:
        st.info("No outstanding or overdue tasks found.")
        return
    task_counts = df_outstanding.groupby(["Person", "Status"]).size().reset_index(name="Count")
    pivot_df = task_counts.pivot(index="Person", columns="Status", values="Count").fillna(0)
    available_statuses = pivot_df.columns.tolist()
    melted_df = pivot_df.reset_index().melt(id_vars="Person", value_vars=available_statuses, var_name="Status", value_name="Count")
    melted_df = melted_df[melted_df["Count"] > 0]
    status_colors = {"Outstanding": "#FFA500", "Overdue": "#FF4136"}
    fig = px.bar(
        melted_df,
        x="Count",
        y="Person",
        color="Status",
        orientation="h",
        title="Outstanding Tasks by Person",
        color_discrete_map=status_colors
    )
    st.subheader("Outstanding Tasks Chart- Due This Week Chart")
    st.plotly_chart(fig)
    st.subheader("Task Counts Table")
    st.write(pivot_df)
    st.divider()

# --- Main Dashboard ---
def main():
    st.title("Dashboard")
    st.markdown("This dashboard displays multiple views of Monday.com data, including Actions By Week, Team Performance, Outstanding Tasks, and Simple Outstanding Tasks, all on a single screen.")

    # Display all dashboards sequentially
    actions_by_week_dashboard()
    team_performance_dashboard()
    outstanding_tasks_dashboard()
    simple_outstanding_tasks_dashboard()

if __name__ == "__main__":
    main()