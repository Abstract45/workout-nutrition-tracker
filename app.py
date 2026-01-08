import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime, timedelta
import re  # For parsing sets

# Database setup
conn = sqlite3.connect('tracker.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS workout_days
             (date TEXT PRIMARY KEY, status TEXT, notes TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS exercise_logs
             (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, exercise_name TEXT, set_number INTEGER, 
              planned_reps TEXT, planned_weight TEXT,
              done_reps TEXT, done_weight TEXT, status TEXT)''')
try:
    c.execute("ALTER TABLE exercise_logs ADD COLUMN set_number INTEGER")
    conn.commit()
except sqlite3.OperationalError:
    pass

c.execute('''DELETE FROM exercise_logs
             WHERE id NOT IN (
                 SELECT MIN(id)
                 FROM exercise_logs
                 GROUP BY date, exercise_name, set_number
             )''')
conn.commit()

try:
    c.execute('''CREATE UNIQUE INDEX IF NOT EXISTS uniq_set ON exercise_logs (date, exercise_name, set_number)''')
    conn.commit()
except sqlite3.OperationalError:
    pass

conn.commit()

# GIF URLs
exercise_gifs = {
    "Bench Press": "https://cdn.jefit.com/assets/img/exercises/gifs/26.gif",
    "Overhead Press": "https://barbend.com/wp-content/uploads/2022/05/barbell-overhead-press-barbend-movement-gif-masters.gif",
    "T-Bar Rows": "https://i.makeagif.com/media/3-31-2024/E3iaRM.gif",
    "Pull-Ups": "http://i.imgur.com/5HP8Cum.gif",
    "T-Bar Deadlifts": "https://legionathletics.com/wp-content/uploads/2024/12/Trap-Bar-Deadlift-gif.gif",
    "Barbell Lunges": "https://www.nerdfitness.com/wp-content/uploads/2020/08/barbell-lunge.gif",
    "Standing Calf Raises": "https://spotebi.com/wp-content/uploads/2015/05/calf-raises-exercise-illustration.gif",
    "Rower Intervals": "https://www.nerdfitness.com/wp-content/uploads/2021/11/row-machine-lean-and-arms.gif",
    "Barbell Curls (optional)": "https://barbend.com/wp-content/uploads/2024/01/barbell-curl-barbend-movement-gif-masters.gif",
    "Treadmill Hills": "https://barbend.com/wp-content/uploads/2024/02/treadmill-run-sprint-barbend-movement-gif-masters.gif",
    "Mix of above": ""
}

# Mobile CSS (full width, no sidebar, scrollable tables)
st.markdown("""
<style>
    .stApp {max-width: 100vw; overflow-x: hidden;}
    section[data-testid="stSidebar"] {display: none !important;}
    .stDataFrame {overflow-x: auto; font-size: 14px;}
    .stButton > button {width: 100%; margin: 0.5rem 0;}
    .stTextArea, .stTextInput {width: 100% !important;}
    .stSelectbox {width: 100% !important;}
    @media (max-width: 640px) {
        .stRadio > div {flex-direction: row; flex-wrap: wrap;}
        .stRadio > div > label {margin: 0.2rem;}
    }
</style>
""", unsafe_allow_html=True)

st.title("Workout Tracker")

# Initialize session state
if 'routine' not in st.session_state:
    st.session_state.routine = None
if 'selected_date' not in st.session_state:
    st.session_state.selected_date = None
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False

# Top navigation dropdown (mobile-friendly)
page = st.selectbox("Navigate", ["Load Routine", "Calendar", "Export"], key="nav_dropdown")

if page == "Load Routine":
    st.header("Load Routine JSON")
    json_input = st.text_area("Paste JSON", height=300)
    uploaded = st.file_uploader("Or upload JSON", type="json")
    if uploaded:
        json_input = uploaded.read().decode("utf-8")
    if st.button("Load JSON"):
        try:
            st.session_state.routine = json.loads(json_input)
            st.success("Loaded! Data saved.")
            with open("routine.json", "w") as f:
                f.write(json_input)  # Save to file for persistence
        except:
            st.error("Invalid JSON")

elif page == "Calendar" and st.session_state.get('routine'):
    st.header("Workout Days")
    
    if st.button("Generate/Refresh Schedule"):
        with st.spinner("Generating..."):
            today = datetime.today()
            end = today + timedelta(days=365)
            current = today
            for phase in st.session_state.routine['phases']:
                # Simplified generation - adjust for your phase logic
                exercises = phase.get('exercises', {}).get("Full Body", [])  # Simplify for your structure
                for ex in exercises:
                    sets_str = str(ex['sets'])
                    nums = re.findall(r'\d+', sets_str)
                    num_sets = max(map(int, nums)) if nums else 1
                    for set_num in range(1, num_sets + 1):
                        # Insert logic (simplified)
                        c.execute("INSERT OR IGNORE INTO exercise_logs (date, exercise_name, set_number, planned_reps, planned_weight, status) VALUES (?, ?, ?, ?, ?, ?)",
                                  ("2026-01-08", ex['name'], set_num, ex['reps'], str(ex.get('start_weight', '0')), "pending"))
                conn.commit()
        st.success("Generated!")
        st.rerun()

    # Vertical list of workout days (mobile-friendly, no chopping)
    df_days = pd.read_sql_query("SELECT date, status FROM workout_days ORDER BY date DESC", conn)
    if not df_days.empty:
        for _, row in df_days.iterrows():
            date_str = row['date']
            mark = "✅ Completed" if row['status'] == "completed" else "- Pending"
            if st.button(f"{date_str} {mark}", key=f"day_{date_str}", use_container_width=True):
                st.session_state.selected_date = date_str
                st.session_state.edit_mode = False
                st.rerun()
    else:
        st.info("No scheduled days. Run Generate Schedule after loading routine.")

    # Details for selected day
    if st.session_state.selected_date:
        date_str = st.session_state.selected_date
        st.subheader(f"Workout for {date_str}")

        c.execute("SELECT notes FROM workout_days WHERE date=?", (date_str,))
        notes_row = c.fetchone()
        current_notes = notes_row[0] if notes_row else ""

        df_sets = pd.read_sql_query("SELECT exercise_name, set_number, planned_reps, planned_weight, done_reps, done_weight, status FROM exercise_logs WHERE date=? ORDER BY exercise_name, set_number", conn, params=(date_str,))

        if not df_sets.empty:
            # GIF buttons
            for ex in df_sets['exercise_name'].unique():
                if st.button(ex, key=f"gif_{ex}_{date_str}", use_container_width=True):
                    st.image(exercise_gifs.get(ex, ""), use_column_width=True)

            if st.session_state.edit_mode:
                notes = st.text_area("Day Notes", current_notes)
                edited = st.data_editor(df_sets, use_container_width=True, height=400)
                if st.button("Save", use_container_width=True):
                    all_completed = all(s == "completed" for s in edited['status'])
                    for _, r in edited.iterrows():
                        c.execute("""UPDATE exercise_logs SET done_reps=?, done_weight=?, status=? WHERE date=? AND exercise_name=? AND set_number=?""",
                                  (r['done_reps'], r['done_weight'], r['status'], date_str, r['exercise_name'], r['set_number']))
                    c.execute("UPDATE workout_days SET status=?, notes=? WHERE date=?", ("completed" if all_completed else "pending", notes, date_str))
                    conn.commit()
                    st.session_state.edit_mode = False
                    st.success("Saved!")
                    st.rerun()
            else:
                st.dataframe(df_sets, use_container_width=True, height=400)
                st.text_area("Day Notes", current_notes, disabled=True)
                if st.button("Edit This Day", use_container_width=True):
                    st.session_state.edit_mode = True
                    st.rerun()
        else:
            st.info("No exercises")

elif page == "Export":
    st.header("Export Data")
    export_type = st.selectbox("Export What?", ["Workout Days", "Exercise Logs", "Both"])
    if export_type in ["Workout Days", "Both"]:
        df_days = pd.read_sql_query("SELECT * FROM workout_days", conn)
        csv = df_days.to_csv(index=False).encode('utf-8')
        st.download_button("Download Days", csv, "days.csv", "text/csv")
    if export_type in ["Exercise Logs", "Both"]:
        df_ex = pd.read_sql_query("SELECT * FROM exercise_logs", conn)
        csv = df_ex.to_csv(index=False).encode('utf-8')
        st.download_button("Download Logs", csv, "logs.csv", "text/csv")

# Load saved routine if not in session
if st.session_state.get('routine') is None:
    try:
        with open("routine.json", "r") as f:
            st.session_state.routine = json.loads(f.read())
        st.info("Loaded saved routine.")
    except FileNotFoundError:
        st.warning("No saved routine. Load one.")
