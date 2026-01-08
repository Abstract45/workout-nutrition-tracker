import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime, timedelta
import re  # For parsing sets
from streamlit_calendar import calendar  # Mobile-friendly calendar component

# Database setup
conn = sqlite3.connect('tracker.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS workout_days
             (date TEXT PRIMARY KEY, status TEXT, notes TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS exercise_logs
             (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, exercise_name TEXT, set_number INTEGER, 
              planned_reps TEXT, planned_weight TEXT,
              done_reps TEXT, done_weight TEXT, status TEXT)''')
# Migrate: Add set_number if missing
try:
    c.execute("ALTER TABLE exercise_logs ADD COLUMN set_number INTEGER")
    conn.commit()
except sqlite3.OperationalError:
    pass

# Remove duplicates
c.execute('''DELETE FROM exercise_logs
             WHERE id NOT IN (
                 SELECT MIN(id)
                 FROM exercise_logs
                 GROUP BY date, exercise_name, set_number
             )''')
conn.commit()

# Unique index
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

# Mobile-friendly CSS
st.markdown("""
<style>
    .stApp {
        max-width: 100vw;
        overflow-x: hidden;
    }
    .stDataFrame {
        font-size: 14px;
        overflow-x: auto;
    }
    .stImage {
        max-width: 100%;
    }
    @media (max-width: 640px) {
        .stRadio > div {
            flex-direction: row;
            flex-wrap: wrap;
        }
        .stRadio > div > label {
            margin: 0.2rem;
        }
    }
</style>
""", unsafe_allow_html=True)

st.title("Workout Tracker")

# Top navigation (mobile-friendly horizontal radio)
page = st.radio("Section", ["Load Routine", "Calendar", "Export"], horizontal=True)

if 'routine' not in st.session_state:
    st.session_state.routine = None

if page == "Load Routine":
    st.header("Load Routine JSON")
    json_input = st.text_area("Paste JSON", height=300)
    uploaded = st.file_uploader("Or upload JSON", type="json")
    if uploaded:
        json_input = uploaded.read().decode("utf-8")
    if st.button("Load JSON"):
        try:
            st.session_state.routine = json.loads(json_input)
            st.success("Loaded!")
        except:
            st.error("Invalid JSON")

elif page == "Calendar" and st.session_state.routine:
    st.header("Workout Calendar")
    
    if st.button("Generate/Refresh Schedule"):
        with st.spinner("Generating..."):
            today = datetime.today()
            end = today + timedelta(days=365)
            current = today
            for phase in st.session_state.routine['phases']:
                # Phase duration logic (simplified)
                exercises = phase.get('exercises', {}).get("Full Body", [])  # Adjust for splits if needed
                for ex in exercises:
                    sets_str = str(ex['sets'])
                    nums = re.findall(r'\d+', sets_str)
                    num_sets = max(map(int, nums)) if nums else 1
                    for set_num in range(1, num_sets + 1):
                        # Insert logic (simplified - adjust for your phases)
                        c.execute("INSERT OR IGNORE INTO exercise_logs (date, exercise_name, set_number, planned_reps, planned_weight, status) VALUES (?, ?, ?, ?, ?, ?)",
                                  ("2026-01-08", ex['name'], set_num, ex['reps'], str(ex.get('start_weight', '0')), "pending"))
                conn.commit()
        st.success("Generated!")

    # Fetch dates for calendar
    df_days = pd.read_sql_query("SELECT date, status FROM workout_days", conn)
    events = []
    for _, row in df_days.iterrows():
        color = "#28a745" if row['status'] == "completed" else "#dc3545"
        events.append({
            "title": "",
            "start": row['date'],
            "backgroundColor": color,
            "borderColor": color,
            "extendedProps": {"date": row['date']}
        })

    cal_options = {
        "initialView": "dayGridMonth",
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": ""},
        "height": "auto"
    }

    cal = calendar(events=events, options=cal_options, key="main_cal")

    if cal and "dateClick" in cal:
        date_str = cal["dateClick"]["date"][:10]  # YYYY-MM-DD
        st.subheader(f"Details for {date_str}")

        # Day notes
        c.execute("SELECT notes FROM workout_days WHERE date=?", (date_str,))
        notes_row = c.fetchone()
        current_notes = notes_row[0] if notes_row else ""

        # Exercises table
        df_sets = pd.read_sql_query("SELECT exercise_name, set_number, planned_reps, planned_weight, done_reps, done_weight, status FROM exercise_logs WHERE date=?", conn, params=(date_str,))
        df_sets = df_sets.sort_values(['exercise_name', 'set_number'])

        if not df_sets.empty:
            unique_ex = df_sets['exercise_name'].unique()
            for ex in unique_ex:
                if st.button(ex, key=f"gif_{ex}_{date_str}"):
                    gif = exercise_gifs.get(ex, "")
                    if gif:
                        st.image(gif, use_column_width=True)
                    else:
                        st.info("No GIF")

            if st.button("Edit This Day"):
                st.session_state.edit_mode = True
                st.rerun()

            if st.session_state.get('edit_mode', False):
                notes = st.text_area("Day Notes", current_notes)
                edited = st.data_editor(df_sets, use_container_width=True, height=400)
                if st.button("Save"):
                    all_done = all(s == "completed" for s in edited['status'])
                    for _, r in edited.iterrows():
                        c.execute("""UPDATE exercise_logs SET done_reps=?, done_weight=?, status=? WHERE date=? AND exercise_name=? AND set_number=?""",
                                  (r['done_reps'], r['done_weight'], r['status'], date_str, r['exercise_name'], r['set_number']))
                    c.execute("UPDATE workout_days SET status=?, notes=? WHERE date=?", ("completed" if all_done else "pending", notes, date_str))
                    conn.commit()
                    del st.session_state.edit_mode
                    st.success("Saved!")
                    st.rerun()
            else:
                st.dataframe(df_sets, use_container_width=True, height=400)
                st.text_area("Day Notes", current_notes, disabled=True)
        else:
            st.info("No exercises")

elif page == "Export":
    # Export code same as before

if not st.session_state.routine:
    st.warning("Load routine first")
