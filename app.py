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
             (user_id TEXT, date TEXT, status TEXT, notes TEXT, PRIMARY KEY (user_id, date))''')
c.execute('''CREATE TABLE IF NOT EXISTS exercise_logs
             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, date TEXT, exercise_name TEXT, set_number INTEGER, 
              planned_reps TEXT, planned_weight TEXT,
              done_reps TEXT, done_weight TEXT, status TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS user_routines
             (user_id TEXT PRIMARY KEY, routine_json TEXT)''')
try:
    c.execute('''CREATE UNIQUE INDEX IF NOT EXISTS uniq_set ON exercise_logs (user_id, date, exercise_name, set_number)''')
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

# Google OAuth login
def login_screen():
    st.header("Private App")
    st.subheader("Log in with Google")
    if st.button("Log in with Google", on_click=st.login):
        pass

if not st.user.is_logged_in:
    login_screen()
else:
    user_id = st.user.email  # Use email as user_id for uniqueness
    st.write(f"Logged in as: {st.user.name}")
    if st.button("Logout"):
        st.logout()
        st.rerun()

    # Load routine from DB if not in session
    if 'routine' not in st.session_state:
        c.execute("SELECT routine_json FROM user_routines WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row and row[0]:
            st.session_state.routine = json.loads(row[0])
        else:
            st.session_state.routine = None

    # Top navigation dropdown (mobile-friendly)
    page = st.selectbox("Navigate", ["Load Routine", "Calendar", "Export"])

    if page == "Load Routine":
        st.header("Load Routine JSON")
        json_input = st.text_area("Paste JSON here", height=300)
        uploaded = st.file_uploader("Or upload JSON", type="json")
        if uploaded:
            json_input = uploaded.read().decode("utf-8")
        if st.button("Load JSON"):
            try:
                st.session_state.routine = json.loads(json_input)
                # Save to DB for persistence
                c.execute("REPLACE INTO user_routines (user_id, routine_json) VALUES (?, ?)", (user_id, json_input))
                conn.commit()
                st.success("Loaded and saved for your user!")
            except:
                st.error("Invalid JSON")

    elif page == "Calendar":
        if st.session_state.routine is None:
            st.warning("Load routine first.")
        else:
            st.header("Workout Days")
            
            if st.button("Generate/Refresh Schedule"):
                with st.spinner("Generating..."):
                    today = datetime.today()
                    current = today
                    for phase in st.session_state.routine['phases']:
                        # Simplified generation - adjust for your phase logic
                        duration_days = 90  # Approx 3 months for phase
                        phase_end = current + timedelta(days=duration_days)
                        while current < phase_end:
                            weekday = current.weekday()
                            # Match schedule (simplified - use your logic)
                            date_str = current.strftime("%Y-%m-%d")
                            c.execute("INSERT OR IGNORE INTO workout_days (user_id, date, status) VALUES (?, ?, ?)", (user_id, date_str, "pending"))
                            # Add exercises (simplified)
                            exercises = phase.get('exercises', {}).get("Full Body", [])
                            for ex in exercises:
                                sets_str = str(ex['sets'])
                                nums = re.findall(r'\d+', sets_str)
                                num_sets = max(map(int, nums)) if nums else 1
                                for set_num in range(1, num_sets + 1):
                                    c.execute("INSERT OR IGNORE INTO exercise_logs (user_id, date, exercise_name, set_number, planned_reps, planned_weight, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                              (user_id, date_str, ex['name'], set_num, ex['reps'], str(ex.get('start_weight', '0')), "pending"))
                            conn.commit()
                            current += timedelta(days=1)
                st.success("Generated!")
                st.rerun()

            # Vertical list of workout days (mobile-friendly, no chopping)
            df_days = pd.read_sql_query("SELECT date, status FROM workout_days WHERE user_id=? ORDER BY date DESC", conn, params=(user_id,))
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

                c.execute("SELECT notes FROM workout_days WHERE user_id=? AND date=?", (user_id, date_str))
                notes_row = c.fetchone()
                current_notes = notes_row[0] if notes_row else ""

                df_sets = pd.read_sql_query("SELECT exercise_name, set_number, planned_reps, planned_weight, done_reps, done_weight, status FROM exercise_logs WHERE user_id=? AND date=? ORDER BY exercise_name, set_number", conn, params=(user_id, date_str))

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
                                c.execute("""UPDATE exercise_logs SET done_reps=?, done_weight=?, status=? WHERE user_id=? AND date=? AND exercise_name=? AND set_number=?""",
                                          (r['done_reps'], r['done_weight'], r['status'], user_id, date_str, r['exercise_name'], r['set_number']))
                            c.execute("UPDATE workout_days SET status=?, notes=? WHERE user_id=? AND date=?", ("completed" if all_completed else "pending", notes, user_id, date_str))
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
        df_days = pd.read_sql_query("SELECT * FROM workout_days WHERE user_id=?", conn, params=(user_id,))
        csv = df_days.to_csv(index=False).encode('utf-8')
        st.download_button("Download Days", csv, "days.csv", "text/csv")
    if export_type in ["Exercise Logs", "Both"]:
        df_ex = pd.read_sql_query("SELECT * FROM exercise_logs WHERE user_id=?", conn, params=(user_id,))
        csv = df_ex.to_csv(index=False).encode('utf-8')
        st.download_button("Download Logs", csv, "logs.csv", "text/csv")
