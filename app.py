import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime, timedelta
import calendar

# Database setup
conn = sqlite3.connect('tracker.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS workout_days
             (date TEXT PRIMARY KEY, status TEXT, notes TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS exercise_logs
             (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, exercise_name TEXT, set_number INTEGER, 
              planned_reps TEXT, planned_weight TEXT,
              done_reps TEXT, done_weight TEXT, status TEXT)''')  # Per set, no notes per
conn.commit()

# App layout
st.title("Calendar-Based Workout Tracker")
st.markdown("Load your routine JSON, view monthly calendar with status marks, and log days. Logging is now per-set in a single table.")

# Sidebar
page = st.sidebar.selectbox("Section", ["Load Routine", "Monthly Calendar", "Export"])

# Global routine var
if 'routine' not in st.session_state:
    st.session_state.routine = None

def get_weekday_name(day_index):
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return weekdays[day_index]

if page == "Load Routine":
    st.header("Load Workout Routine JSON")
    json_input = st.text_area("Paste JSON here", height=300)
    uploaded_file = st.file_uploader("Or upload JSON file", type="json")
    
    if uploaded_file:
        json_input = uploaded_file.read().decode("utf-8")
    
    if st.button("Load JSON"):
        try:
            st.session_state.routine = json.loads(json_input)
            st.success("Routine loaded! Go to Monthly Calendar.")
        except json.JSONDecodeError:
            st.error("Invalid JSON format.")

elif page == "Monthly Calendar" and st.session_state.routine:
    st.header("Workout Calendar (Monthly View)")
    
    # Generate schedule if not already
    if st.button("Generate/Refresh Schedule"):
        progress_bar = st.progress(0)
        today = datetime.today()
        absolute_end = today + timedelta(days=365)
        phase_start = today
        total_days = 0
        for i, phase in enumerate(st.session_state.routine['phases']):
            months = phase['months'].split('-')
            duration_months = int(months[1]) - int(months[0]) + 1
            phase_end = min(phase_start + timedelta(days=30 * duration_months), absolute_end)  
            
            current = phase_start
            while current < phase_end:
                weekday = get_weekday_name(current.weekday())
                if any(weekday in s for s in phase['schedule']):
                    sched_entry = next((s for s in phase['schedule'] if weekday in s), None)
                    if sched_entry:
                        workout_type = sched_entry.split(' (')[-1].rstrip(')') if '(' in sched_entry else "Full Body"
                        date_str = current.strftime("%Y-%m-%d")
                        
                        # Insert day
                        c.execute("INSERT OR IGNORE INTO workout_days (date, status, notes) VALUES (?, ?, ?)",
                                  (date_str, "pending", phase.get('notes', '')))
                        
                        # Insert per-set rows
                        exercises = phase.get('exercises', {}).get(workout_type, [])
                        for ex in exercises:
                            for set_num in range(1, int(ex['sets']) + 1 if isinstance(ex['sets'], int) else 1):  # Handle "4-5" as 4 for initial
                                c.execute("INSERT OR IGNORE INTO exercise_logs (date, exercise_name, set_number, planned_reps, planned_weight, status) VALUES (?, ?, ?, ?, ?, ?)",
                                          (date_str, ex['name'], set_num, ex['reps'], str(ex.get('start_weight', '0')), "pending"))
                        conn.commit()
                current += timedelta(days=1)
                total_days += 1
                progress_bar.progress(min(total_days / 365, 1.0))
            
            phase_start = phase_end
        st.success("Schedule generated/updated!")
    
    # Select year and month
    today = datetime.today()
    year = st.selectbox("Select Year", range(today.year - 5, today.year + 6), index=5)
    month_num = st.selectbox("Select Month", list(range(1, 13)), index=today.month - 1, format_func=lambda x: calendar.month_name[x])
    
    # Build interactive calendar with buttons
    cal = calendar.monthcalendar(year, month_num)
    df_days = pd.read_sql_query("SELECT date, status FROM workout_days", conn)
    df_days['date'] = pd.to_datetime(df_days['date'])
    df_days_month = df_days[(df_days['date'].dt.year == year) & (df_days['date'].dt.month == month_num)]
    
    st.subheader(calendar.month_name[month_num] + " " + str(year))
    headers = st.columns(7)
    for i, day in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        headers[i].write(day)
    
    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                cols[i].write("")
            else:
                date_str = f"{year}-{month_num:02d}-{day:02d}"
                row = df_days_month[df_days_month['date'] == date_str]
                if not row.empty:
                    status = row['status'].values[0]
                    mark = "✅" if status == "completed" else "-"
                    label = f"{day} {mark}"
                else:
                    label = str(day)
                
                if cols[i].button(label, key=f"cal_btn_{date_str}"):
                    st.session_state.selected_date = date_str
                    st.session_state.edit_mode = False  # Start in view mode
                    st.rerun()  # Rerun to show log below
    
    st.info("✅ = Completed, - = Pending/Rescheduled. Click a day to view/log details below.")
    
    # Show view/edit for selected date if clicked
    if 'selected_date' in st.session_state:
        date_str = st.session_state.selected_date
        st.subheader(f"Details for {date_str}")
        
        # Day notes
        c.execute("SELECT notes FROM workout_days WHERE date=?", (date_str,))
        row = c.fetchone()
        current_notes = row[0] if row else ""
        
        # Fetch set rows
        df_sets = pd.read_sql_query("SELECT exercise_name, set_number, planned_reps, planned_weight, done_reps, done_weight, status FROM exercise_logs WHERE date=?", conn, params=(date_str,))
        df_sets = df_sets.sort_values(['exercise_name', 'set_number'])
        
        if not df_sets.empty:
            if st.session_state.get('edit_mode', False):
                # Edit mode: Editable table
                notes = st.text_area("Day Notes", value=current_notes, key="day_notes_selected_edit")
                edited_df = st.data_editor(
                    df_sets,
                    column_config={
                        "exercise_name": st.column_config.TextColumn("Exercise", disabled=True),
                        "set_number": st.column_config.NumberColumn("Set", disabled=True),
                        "planned_reps": st.column_config.TextColumn("Planned Reps", disabled=True),
                        "planned_weight": st.column_config.TextColumn("Planned Weight", disabled=True),
                        "done_reps": "Done Reps",
                        "done_weight": "Done Weight",
                        "status": st.column_config.SelectboxColumn("Status", options=["pending", "completed"]),
                    },
                    num_rows="dynamic",
                    hide_index=True,
                    use_container_width=True
                )
                
                if st.button("Save Changes"):
                    all_completed = all(s == "completed" for s in edited_df['status'])
                    for idx, row in edited_df.iterrows():
                        c.execute("""UPDATE exercise_logs SET done_reps=?, done_weight=?, status=?
                                     WHERE date=? AND exercise_name=? AND set_number=?""",
                                  (row['done_reps'], row['done_weight'], row['status'], date_str, row['exercise_name'], row['set_number']))
                    conn.commit()
                    
                    day_status = "completed" if all_completed else "pending"
                    c.execute("UPDATE workout_days SET status=?, notes=? WHERE date=?", (day_status, notes, date_str))
                    conn.commit()
                    st.session_state.edit_mode = False
                    st.success("Saved! Now in view mode.")
                    st.rerun()
            else:
                # View mode: Read-only table
                st.dataframe(
                    df_sets,
                    column_config={
                        "exercise_name": "Exercise",
                        "set_number": "Set",
                        "planned_reps": "Planned Reps",
                        "planned_weight": "Planned Weight",
                        "done_reps": "Done Reps",
                        "done_weight": "Done Weight",
                        "status": "Status",
                    },
                    hide_index=True,
                    use_container_width=True
                )
                st.text_area("Day Notes", value=current_notes, disabled=True)
                
                if st.button("Edit This Day"):
                    st.session_state.edit_mode = True
                    st.rerun()
        else:
            st.info("No exercises scheduled for this day.")

elif page == "Export":
    st.header("Export Data")
    export_type = st.selectbox("Export What?", ["Workout Days", "Exercise Logs", "Both"])
    
    if export_type in ["Workout Days", "Both"]:
        df_days = pd.read_sql_query("SELECT * FROM workout_days", conn)
        csv_days = df_days.to_csv(index=False).encode('utf-8')
        st.download_button("Download Workout Days CSV", csv_days, "workout_days.csv", "text/csv")
    
    if export_type in ["Exercise Logs", "Both"]:
        df_ex = pd.read_sql_query("SELECT * FROM exercise_logs", conn)
        csv_ex = df_ex.to_csv(index=False).encode('utf-8')
        st.download_button("Download Exercise Logs CSV", csv_ex, "exercise_logs.csv", "text/csv")

if not st.session_state.routine:
    st.warning("Load routine first in 'Load Routine' section.")
