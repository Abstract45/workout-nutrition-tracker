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
             (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, exercise_name TEXT, 
              planned_sets TEXT, planned_reps TEXT, planned_weight TEXT,
              done_sets TEXT, done_reps TEXT, done_weight TEXT, notes TEXT, status TEXT)''')
# Migrate: Add status column if missing
try:
    c.execute("ALTER TABLE exercise_logs ADD COLUMN status TEXT")
    conn.commit()
except sqlite3.OperationalError:
    pass  # Column already exists
conn.commit()

# App layout
st.title("Calendar-Based Workout Tracker")
st.markdown("Load your routine JSON, view monthly calendar with status marks, and log days. Logging is now per-exercise with individual status.")

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
            st.success("Routine loaded! Go to Monthly Calendar or Log Day.")
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
                        
                        # Exercises with initial status
                        exercises = phase.get('exercises', {}).get(workout_type, [])
                        
                        for ex in exercises:
                            c.execute("INSERT OR IGNORE INTO exercise_logs (date, exercise_name, planned_sets, planned_reps, planned_weight, status) VALUES (?, ?, ?, ?, ?, ?)",
                                      (date_str, ex['name'], str(ex['sets']), ex['reps'], str(ex.get('start_weight', '0')), "pending"))
                        conn.commit()
                current += timedelta(days=1)
                total_days += 1
                progress_bar.progress(min
