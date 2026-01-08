import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime, timedelta

# Database setup for checkmarks
conn = sqlite3.connect('tracker.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS workout_days
             (date TEXT PRIMARY KEY, status TEXT, notes TEXT, workout_details TEXT)''')  # Added workout_details for exercises
conn.commit()

# App layout
st.title("Calendar-Based Workout Tracker")
st.markdown("Load your routine JSON, view/edit calendar as a table, check off days, and track progress.")

# Sidebar
page = st.sidebar.selectbox("Section", ["Load Routine", "Calendar View", "Log Day", "Export"])

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
            st.success("Routine loaded! Go to Calendar View to generate schedule.")
        except json.JSONDecodeError:
            st.error("Invalid JSON format.")

elif page == "Calendar View" and st.session_state.routine:
    st.header("Workout Calendar (Table View)")
    
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
            phase_end = min(phase_start + timedelta(days=30 * duration_months), absolute_end)  # Approx, cap total
            
            current = phase_start
            phase_days = (phase_end - phase_start).days
            while current < phase_end:
                weekday = get_weekday_name(current.weekday())
                if any(weekday in s for s in phase['schedule']):
                    sched_entry = next((s for s in phase['schedule'] if weekday in s), None)
                    if sched_entry:
                        workout_type = sched_entry.split(' (')[-1].rstrip(')') if '(' in sched_entry else "Full Body"
                        date_str = current.strftime("%Y-%m-%d")
                        exercises_json = json.dumps(phase.get('exercises', {}))  # Store exercises
                        
                        # Insert if not exists
                        c.execute("INSERT OR IGNORE INTO workout_days (date, status, notes, workout_details) VALUES (?, ?, ?, ?)",
                                  (date_str, "pending", phase.get('notes', ''), exercises_json))
                        conn.commit()
                current += timedelta(days=1)
                total_days += 1
                progress_bar.progress(min(total_days / 365, 1.0))  # Update progress
            
            phase_start = phase_end
        st.success("Schedule generated/updated!")
    
    # Display editable table
    df = pd.read_sql_query("SELECT date, status, notes, workout_details FROM workout_days ORDER BY date", conn)
    if not df.empty:
        df['workout_details'] = df['workout_details'].apply(lambda x: json.loads(x) if x else {})  # Parse JSON for display
        edited_df = st.data_editor(
            df,
            column_config={
                "date": "Date",
                "status": st.column_config.SelectboxColumn(options=["pending", "completed", "rescheduled"]),
                "notes": "Notes",
                "workout_details": st.column_config.TextColumn("Workout Details (JSON)"),
            },
            use_container_width=True,
            num_rows="dynamic"  # Allow adding/rescheduling new rows
        )
        
        # Save edits back to DB
        if st.button("Save Changes"):
            for idx, row in edited_df.iterrows():
                workout_details_str = json.dumps(row['workout_details']) if isinstance(row['workout_details'], dict) else row['workout_details']
                c.execute("REPLACE INTO workout_days VALUES (?, ?, ?, ?)",
                          (row['date'], row['status'], row['notes'], workout_details_str))
            conn.commit()
            st.success("Changes saved!")
    else:
        st.info("No schedule yet—click 'Generate/Refresh Schedule' after loading routine.")

elif page == "Log Day":
    st.header("Log/Check Off a Day")
    date = st.date_input("Select Date", datetime.today())
    date_str = str(date)
    
    c.execute("SELECT status, notes, workout_details FROM workout_days WHERE date=?", (date_str,))
    row = c.fetchone()
    current_status = row[0] if row else "pending"
    current_notes = row[1] if row else ""
    current_details = json.loads(row[2]) if row and row[2] else {}
    
    status = st.selectbox("Status", ["pending", "completed", "rescheduled"], index=["pending", "completed", "rescheduled"].index(current_status))
    notes = st.text_area("Notes", value=current_notes)
    details_json = st.text_area("Workout Details (JSON)", value=json.dumps(current_details, indent=2))
    
    if st.button("Save"):
        c.execute("REPLACE INTO workout_days VALUES (?, ?, ?, ?)", (date_str, status, notes, details_json))
        conn.commit()
        st.success("Day updated!")

elif page == "Export":
    st.header("Export Data")
    df = pd.read_sql_query("SELECT * FROM workout_days", conn)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv, "workout_days.csv", "text/csv")

if not st.session_state.routine:
    st.warning("Load routine first in 'Load Routine' section.")
