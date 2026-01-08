import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime, timedelta
from streamlit_calendar import calendar

# Database setup
conn = sqlite3.connect('tracker.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS workout_days
             (date TEXT PRIMARY KEY, status TEXT, notes TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS exercise_logs
             (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, exercise_name TEXT, 
              planned_sets TEXT, planned_reps TEXT, planned_weight TEXT,
              done_sets TEXT, done_reps TEXT, done_weight TEXT, notes TEXT)''')
conn.commit()

# App layout
st.title("Calendar-Based Workout Tracker")
st.markdown("Load your routine JSON, view calendar, select days to log exercises.")

# Sidebar
page = st.sidebar.selectbox("Section", ["Load Routine", "Calendar & Log", "Export"])

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
            st.success("Routine loaded! Go to Calendar & Log.")
        except json.JSONDecodeError:
            st.error("Invalid JSON format.")

elif page == "Calendar & Log" and st.session_state.routine:
    st.header("Workout Calendar")
    
    # Generate schedule if not already in DB (or refresh)
    if st.button("Generate/Refresh Schedule"):
        progress_bar = st.progress(0)
        today = datetime.today()
        absolute_end = today + timedelta(days=365)  # Cap at 1 year max
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
                        
                        # Insert day if not exists
                        c.execute("INSERT OR IGNORE INTO workout_days (date, status, notes) VALUES (?, ?, ?)",
                                  (date_str, "pending", phase.get('notes', '')))
                        
                        # Get exercises for this type (now always dict)
                        exercises = phase.get('exercises', {}).get(workout_type, [])
                        
                        # Insert individual exercises
                        for ex in exercises:
                            c.execute("INSERT OR IGNORE INTO exercise_logs (date, exercise_name, planned_sets, planned_reps, planned_weight) VALUES (?, ?, ?, ?, ?)",
                                      (date_str, ex['name'], str(ex['sets']), ex['reps'], str(ex.get('start_weight', '0'))))
                        conn.commit()
                current += timedelta(days=1)
                total_days += 1
                progress_bar.progress(min(total_days / 365, 1.0))
            
            phase_start = phase_end
        st.success("Schedule generated/updated!")
    
    # Fetch all days for calendar events
    df_days = pd.read_sql_query("SELECT date, status, notes FROM workout_days ORDER BY date", conn)
    events = []
    for _, row in df_days.iterrows():
        title = "✔" if row['status'] == "completed" else "X"
        color = "#00FF00" if row['status'] == "completed" else "#FF0000"
        events.append({
            "title": title,
            "start": row['date'],
            "color": color,
            "extendedProps": {"notes": row['notes']}
        })
    
    # Display calendar
    calendar_options = {
        "initialView": "dayGridMonth",
        "editable": False,
    }
    cal = calendar(events=events, options=calendar_options)
    
    # Get selected date from calendar callback (if clicked)
    selected_date = None
    if cal and 'dateClick' in cal:
        selected_date = cal['dateClick']['date'].split('T')[0]  # Format YYYY-MM-DD
    
    # If selected, show log for that day
    if selected_date:
        st.subheader(f"Log for {selected_date}")
        date_str = selected_date
        
        # Day info
        c.execute("SELECT status, notes FROM workout_days WHERE date=?", (date_str,))
        row = c.fetchone()
        current_status = row[0] if row else "pending"
        current_notes = row[1] if row else ""
        
        status = st.selectbox("Status", ["pending", "completed", "rescheduled"], index=["pending", "completed", "rescheduled"].index(current_status))
        notes = st.text_area("Day Notes", value=current_notes)
        
        # Exercises sub-table
        st.subheader("Exercises")
        df_ex = pd.read_sql_query("SELECT exercise_name, planned_sets, planned_reps, planned_weight, done_sets, done_reps, done_weight, notes FROM exercise_logs WHERE date=?", conn, params=(date_str,))
        if not df_ex.empty:
            edited_ex = st.data_editor(
                df_ex,
                column_config={
                    "exercise_name": "Exercise",
                    "planned_sets": "Planned Sets",
                    "planned_reps": "Planned Reps",
                    "planned_weight": "Planned Weight",
                    "done_sets": "Done Sets",
                    "done_reps": "Done Reps",
                    "done_weight": "Done Weight",
                    "notes": "Exercise Notes",
                },
                use_container_width=True,
                hide_index=False
            )
        else:
            edited_ex = pd.DataFrame()
            st.info("No exercises scheduled.")
        
        if st.button("Save"):
            # Save day
            c.execute("REPLACE INTO workout_days VALUES (?, ?, ?)", (date_str, status, notes))
            
            # Save exercises
            for idx, row in edited_ex.iterrows():
                c.execute("""UPDATE exercise_logs SET done_sets=?, done_reps=?, done_weight=?, notes=?
                             WHERE date=? AND exercise_name=?""",
                          (row['done_sets'], row['done_reps'], row['done_weight'], row['notes'], date_str, row['exercise_name']))
            conn.commit()
            st.success("Saved! Refresh calendar to see updates.")

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
