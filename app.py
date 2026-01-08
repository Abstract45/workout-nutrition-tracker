import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime, timedelta
import calendar as py_calendar
from streamlit_calendar import calendar  # For calendar view

# Database setup for checkmarks
conn = sqlite3.connect('tracker.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS workout_days
             (date TEXT PRIMARY KEY, status TEXT, notes TEXT)''')  # status: 'pending', 'completed', 'rescheduled'
conn.commit()

# App layout
st.title("Calendar-Based Workout Tracker")
st.markdown("Load your routine JSON, view calendar, check off days, and track progress.")

# Sidebar
page = st.sidebar.selectbox("Section", ["Load Routine", "Calendar View", "Log Day", "Export"])

# Global routine var
if 'routine' not in st.session_state:
    st.session_state.routine = None

if page == "Load Routine":
    st.header("Load Workout Routine JSON")
    json_input = st.text_area("Paste JSON here", height=300)
    uploaded_file = st.file_uploader("Or upload JSON file", type="json")
    
    if uploaded_file:
        json_input = uploaded_file.read().decode("utf-8")
    
    if st.button("Load JSON"):
        try:
            st.session_state.routine = json.loads(json_input)
            st.success("Routine loaded! Go to Calendar View.")
        except json.JSONDecodeError:
            st.error("Invalid JSON format.")

elif page == "Calendar View" and st.session_state.routine:
    st.header("Workout Calendar")
    
    # Generate events from routine
    today = datetime.today()
    events = []
    
    # Simple logic: Map phases to dates (assuming start today)
    phase_start = today
    for phase in st.session_state.routine['phases']:
        # Parse months, e.g., "1-3" -> 3 months
        months = phase['months'].split('-')
        duration_months = int(months[1]) - int(months[0]) + 1
        phase_end = phase_start + timedelta(days=30 * duration_months)  # Approx
        
        for day in phase['schedule']:
            current = phase_start
            while current < phase_end:
                if py_calendar.day_name[current.weekday()] in phase['schedule']:  # Match day name
                    date_str = current.strftime("%Y-%m-%d")
                    # Check DB status
                    c.execute("SELECT status FROM workout_days WHERE date=?", (date_str,))
                    row = c.fetchone()
                    status = row[0] if row else "pending"
                    color = "#00FF00" if status == "completed" else "#FF0000" if status == "rescheduled" else "#FFFF00"
                    
                    events.append({
                        "title": f"{phase['name']} - {day}",
                        "start": date_str,
                        "color": color,
                        "extendedProps": {"notes": json.dumps(phase.get('exercises', {}))}  # Store exercises
                    })
                current += timedelta(days=1)
        
        phase_start = phase_end
    
    # Display calendar
    calendar_options = {
        "initialView": "dayGridMonth",
        "editable": True,  # Allow drag to reschedule
    }
    cal = calendar(events=events, options=calendar_options)
    
    # Handle reschedule if dragged
    if cal.get("editedEvents"):
        for ev in cal["editedEvents"]:
            old_date = ev["oldEvent"]["start"]
            new_date = ev["newEvent"]["start"]
            c.execute("UPDATE workout_days SET date=? WHERE date=?", (new_date, old_date))
            conn.commit()
            st.success(f"Rescheduled {old_date} to {new_date}")

elif page == "Log Day":
    st.header("Log/Check Off a Day")
    date = st.date_input("Select Date", datetime.today())
    date_str = str(date)
    
    c.execute("SELECT status, notes FROM workout_days WHERE date=?", (date_str,))
    row = c.fetchone()
    current_status = row[0] if row else "pending"
    
    status = st.selectbox("Status", ["pending", "completed", "rescheduled"], index=["pending", "completed", "rescheduled"].index(current_status))
    notes = st.text_area("Notes", value=row[1] if row else "")
    
    if st.button("Save"):
        c.execute("REPLACE INTO workout_days VALUES (?, ?, ?)", (date_str, status, notes))
        conn.commit()
        st.success("Day updated!")

elif page == "Export":
    st.header("Export Data")
    df = pd.read_sql_query("SELECT * FROM workout_days", conn)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv, "workout_days.csv", "text/csv")

if not st.session_state.routine:
    st.warning("Load routine first in 'Load Routine' section.")
