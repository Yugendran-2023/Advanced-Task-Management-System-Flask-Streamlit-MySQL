from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_cors import CORS
import pymysql
from datetime import datetime, date
import os
import threading
import requests
import streamlit as st
import pandas as pd
import time

app = Flask(__name__)
CORS(app)

# ------------------ DB CONFIG ------------------
def get_db_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="manager",
        database="Project",
        cursorclass=pymysql.cursors.DictCursor
    )

# ------------------ CREATE TABLE ------------------
def create_tasks_table():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
    id INT NOT NULL AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    due_date DATE,
    status ENUM('To Do', 'In Progress', 'Done') DEFAULT 'To Do',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
                )
            """)
            conn.commit()
    except pymysql.MySQLError as err:
        print(f"Error creating tasks table: {err}")
    finally:
        conn.close()

create_tasks_table()

# ------------------ ROUTES ------------------
@app.route('/')
def index():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        tasks = cursor.fetchall()
    conn.close()
    return render_template("index.html", tasks=tasks)

@app.route('/add', methods=['GET', 'POST'])
def add_task():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        due_date = request.form['due_date']
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO tasks (title, description, due_date)
                VALUES (%s, %s, %s)
            """, (title, description, due_date))
            conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template("add.html")

@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM tasks WHERE id=%s", (task_id,))
        task = cursor.fetchone()

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        due_date = request.form['due_date']
        status = request.form['status']
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE tasks SET title=%s, description=%s, due_date=%s, status=%s WHERE id=%s
            """, (title, description, due_date, status, task_id))
            conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn.close()
    return render_template("edit.html", task=task)

@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM tasks WHERE id=%s", (task_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route("/tasks", methods=["GET"])
def get_tasks():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        tasks = cursor.fetchall()
    conn.close()
    return jsonify(tasks)

@app.route("/tasks", methods=["POST"])
def add_task_api():
    data = request.get_json()
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO tasks (title, description, due_date) VALUES (%s, %s, %s)",
            (data['title'], data['description'], data['due_date'])
        )
        conn.commit()
    conn.close()
    return jsonify({"message": "Task added successfully"}), 201

@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.get_json()
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE tasks SET title=%s, description=%s, due_date=%s, status=%s WHERE id=%s",
            (data['title'], data['description'], data['due_date'], data['status'], task_id)
        )
        conn.commit()
    conn.close()
    return jsonify({"message": "Task updated successfully"})

@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task_api(task_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM tasks WHERE id=%s", (task_id,))
        conn.commit()
    conn.close()
    return jsonify({"message": "Task deleted successfully"})

# ------------------ RUN FLASK THREAD ------------------
def run_flask():
    app.run(port=5000, debug=False, use_reloader=False)

flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()
time.sleep(1)

# ------------------ STREAMLIT UI ------------------
st.set_page_config(page_title="📝 Task Manager", layout="wide")
st.markdown("""
    <style>
        .stApp {
            zoom: 1.2;
        }
    </style>
""", unsafe_allow_html=True)

st.title("Schedule Task Management System")

API_URL = "http://localhost:5000"

menu = st.sidebar.radio(" Menu", ["📋 View Tasks", "➕ Add Task", "✏️ Edit Task", "🗑️ Delete Task"])

def fetch_tasks():
    try:
        response = requests.get(f"{API_URL}/tasks")
        if response.status_code == 200:
            return pd.DataFrame(response.json())
    except requests.exceptions.RequestException:
        st.error("⚠️ Could not connect to the Flask server.")
    return pd.DataFrame()

def add_task_to_api(title, description, due_date):
    data = {"title": title, "description": description, "due_date": str(due_date)}
    requests.post(f"{API_URL}/tasks", json=data)

def update_task_in_api(task_id, title, description, due_date, status):
    data = {
        "title": title,
        "description": description,
        "due_date": str(due_date),
        "status": status
    }
    requests.put(f"{API_URL}/tasks/{task_id}", json=data)

def delete_task_from_api(task_id):
    requests.delete(f"{API_URL}/tasks/{task_id}")

if menu == "📋 View Tasks":
    st.subheader("All Tasks")
    df = fetch_tasks()
    if not df.empty:
        df['due_date'] = pd.to_datetime(df['due_date']).dt.date
        st.dataframe(df[['id', 'title', 'description', 'due_date', 'status']], use_container_width=True)
    else:
        st.info("No tasks found.")

elif menu == "➕ Add Task":
    st.subheader("Add Task")
    with st.form("add_form"):
        title = st.text_input("Task Title")
        desc = st.text_area("Description")
        due = st.date_input("Due Date", min_value=date.today())
        submitted = st.form_submit_button("Add Task")
        if submitted:
            if title and desc and due:
                add_task_to_api(title, desc, due)
                st.success("✅ Task added successfully!")
            else:
                st.warning("⚠️ Please fill in all fields.")

elif menu == "✏️ Edit Task":
    st.subheader("Edit Task")
    df = fetch_tasks()
    if not df.empty:
        task_ids = df['id'].tolist()
        selected_id = st.selectbox("Select Task ID", task_ids)
        task = df[df['id'] == selected_id].iloc[0]
        with st.form("edit_form"):
            new_title = st.text_input("Title", value=task['title'])
            new_desc = st.text_area("Description", value=task['description'])
            new_due = st.date_input("Due Date", value=pd.to_datetime(task['due_date']))
            new_status = st.selectbox("Status", ["To Do", "In Progress", "Done"],
                                      index=["To Do", "In Progress", "Done"].index(task['status']))
            submitted = st.form_submit_button("Update Task")
            if submitted:
                update_task_in_api(selected_id, new_title, new_desc, new_due, new_status)
                st.success("✅ Task updated successfully!")
    else:
        st.info("No tasks available to edit.")

elif menu == "🗑️ Delete Task":
    st.subheader("Delete Task")
    df = fetch_tasks()
    if not df.empty:
        task_ids = df['id'].tolist()
        delete_id = st.selectbox("Select Task ID to Delete", task_ids)
        if st.button("Delete"):
            delete_task_from_api(delete_id)
            st.success("🗑️ Task deleted successfully!")
    else:
        st.info("No tasks available to delete.")
