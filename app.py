import streamlit as st
import pandas as pd
import sqlite3
import datetime
import altair as alt  # For charts

# Database setup
conn = sqlite3.connect('tracker.db', check_same_thread=False)
c = conn.cursor()

# Create tables if not exist
c.execute('''CREATE TABLE IF NOT EXISTS workouts
             (date TEXT, exercise TEXT, sets INTEGER, reps TEXT, weight REAL, notes TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS nutrition
             (date TEXT, calories REAL, protein REAL, carbs REAL, fats REAL, notes TEXT)''')
conn.commit()

# Your routine exercises and goals (customized from our plan)
exercises = {
    'Bench Press': {'start': 95, 'goal': 225},
    'Overhead Press': {'start': 65, 'goal': 135},
    'T-Bar Rows': {'start': 45, 'goal': 185},
    'Pull-Ups': {'start': '3-5', 'goal': '12'},  # Bodyweight, reps as string
    'T-Bar Deadlifts': {'start': 135, 'goal': 315},
    'Barbell Lunges': {'start': 45, 'goal': 135},
    'Standing Calf Raises': {'start': 95, 'goal': 225},
    # Add more if needed, e.g., cardio sessions
}

nutrition_targets = {'calories': 2500, 'protein': 160, 'carbs': 310, 'fats': 70}

# App layout
st.title("Workout & Nutrition Tracker")
st.markdown("Log your sessions, track progress, and export data. Based on your back-safe routine.")

# Sidebar for navigation
page = st.sidebar.selectbox("Choose Section", ["Log Workout", "Log Nutrition", "View Progress", "Export Data"])

# Ramadan toggle
ramadan_mode = st.sidebar.checkbox("Ramadan Mode (Reduce volume by 20-30%)")

if page == "Log Workout":
    st.header("Log a Workout")
    date = st.date_input("Date", datetime.date.today())
    exercise = st.selectbox("Exercise", list(exercises.keys()))
    sets = st.number_input("Sets", min_value=1, value=3)
    reps = st.text_input("Reps (e.g., 8-12 or 5,6,7)", "8-12")
    weight = st.number_input("Weight (lbs)", min_value=0.0, value=exercises[exercise]['start'])
    notes = st.text_area("Notes (e.g., form felt good)")
    
    if ramadan_mode:
        st.info("Ramadan adjustment: Suggest reducing sets to " + str(int(sets * 0.7)))
    
    if st.button("Save Workout"):
        c.execute("INSERT INTO workouts VALUES (?, ?, ?, ?, ?, ?)",
                  (str(date), exercise, sets, reps, weight, notes))
        conn.commit()
        st.success("Workout logged!")

elif page == "Log Nutrition":
    st.header("Log Nutrition")
    date = st.date_input("Date", datetime.date.today())
    calories = st.number_input("Calories", min_value=0.0, value=nutrition_targets['calories'])
    protein = st.number_input("Protein (g)", min_value=0.0, value=nutrition_targets['protein'])
    carbs = st.number_input("Carbs (g)", min_value=0.0, value=nutrition_targets['carbs'])
    fats = st.number_input("Fats (g)", min_value=0.0, value=nutrition_targets['fats'])
    notes = st.text_area("Notes (e.g., meal sources)")
    
    if ramadan_mode:
        st.info("Ramadan tip: Focus on high-protein iftar and carb-heavy suhoor.")
    
    if st.button("Save Nutrition"):
        c.execute("INSERT INTO nutrition VALUES (?, ?, ?, ?, ?, ?)",
                  (str(date), calories, protein, carbs, fats, notes))
        conn.commit()
        st.success("Nutrition logged!")

elif page == "View Progress":
    st.header("Progress Dashboard")
    
    # Workouts
    st.subheader("Workouts")
    df_workouts = pd.read_sql_query("SELECT * FROM workouts", conn)
    if not df_workouts.empty:
        st.dataframe(df_workouts)
        
        # Chart: Weight progression per exercise
        for ex in df_workouts['exercise'].unique():
            df_ex = df_workouts[df_workouts['exercise'] == ex].sort_values('date')
            chart = alt.Chart(df_ex).mark_line().encode(
                x='date:T',
                y='weight:Q',
                tooltip=['date', 'weight', 'reps']
            ).properties(title=f"{ex} Progress (Goal: {exercises.get(ex, {}).get('goal', 'N/A')})")
            st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No workouts logged yet.")
    
    # Nutrition
    st.subheader("Nutrition")
    df_nut = pd.read_sql_query("SELECT * FROM nutrition", conn)
    if not df_nut.empty:
        st.dataframe(df_nut)
        
        # Chart: Protein over time
        chart_prot = alt.Chart(df_nut).mark_bar().encode(
            x='date:T',
            y='protein:Q',
            tooltip=['date', 'protein']
        ).properties(title=f"Protein Intake (Target: {nutrition_targets['protein']}g)")
        st.altair_chart(chart_prot, use_container_width=True)
    else:
        st.info("No nutrition logged yet.")

elif page == "Export Data":
    st.header("Export Data")
    export_type = st.selectbox("Export What?", ["Workouts", "Nutrition", "Both"])
    
    if export_type == "Workouts" or export_type == "Both":
        df_workouts = pd.read_sql_query("SELECT * FROM workouts", conn)
        csv_work = df_workouts.to_csv(index=False).encode('utf-8')
        st.download_button("Download Workouts CSV", csv_work, "workouts.csv", "text/csv")
    
    if export_type == "Nutrition" or export_type == "Both":
        df_nut = pd.read_sql_query("SELECT * FROM nutrition", conn)
        csv_nut = df_nut.to_csv(index=False).encode('utf-8')
        st.download_button("Download Nutrition CSV", csv_nut, "nutrition.csv", "text/csv")
    
    st.info("To check with me: Download CSV, open in Excel/Notepad, copy recent rows, and paste into our chat (e.g., 'Review this log: [paste data]'). I'll analyze progress toward your year goals.")

### Code for `requirements.txt`
