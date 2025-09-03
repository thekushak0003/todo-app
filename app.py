# app.py

import os
import google.generativeai as genai
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from dotenv import load_dotenv

load_dotenv()

# --- AI Configuration ---
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel('gemini-pro')
    print("AI Model configured successfully.")
except Exception as e:
    print(f"Error configuring AI Model: {e}")
    model = None

# --- Flask App Initialization ---
app = Flask(__name__)
# A secret key is required for flash messages
app.secret_key = os.urandom(24)

# --- Database Initialization ---
def init_db():
    conn = sqlite3.connect('database.db')
    print("Opened database successfully")
    # NEW: Added a 'status' column to tasks table with a default value
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'incomplete'
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS subtasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            task_id INTEGER NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks (id)
        )
    ''')
    print("Tables created successfully")
    conn.close()

init_db()

# --- AI Helper Function (Unchanged) ---
def generate_subtasks(task_content):
    if not model:
        return ["AI model not available."]
    prompt = f"""You are a project management assistant. Your goal is to break down a larger task into 2-4 smaller, actionable sub-tasks.
    - If the task is already simple (e.g., "Call mom"), just return the original task.
    - Otherwise, provide a list of sub-tasks.
    - Respond ONLY with a Python-style list of strings. Do not include any other text or explanation.
    Example 1: Task: "Plan birthday party", Response: ["Create guest list", "Send out invitations", "Order a cake", "Plan party games"]
    Example 2: Task: "Read a book", Response: ["Read a book"]
    Now, break down this task: "{task_content}" """
    try:
        response = model.generate_content(prompt)
        subtasks_str = response.text.strip().replace('[', '').replace(']', '').replace('"', "'")
        subtasks = [item.strip().strip("'") for item in subtasks_str.split("',") if item]
        return subtasks
    except Exception as e:
        print(f"AI generation failed: {e}")
        return ["Failed to generate sub-tasks."]

# --- Flask Routes ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        main_task_content = request.form['content']
        if main_task_content:
            conn = sqlite3.connect('database.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tasks (content) VALUES (?)", (main_task_content,))
            new_task_id = cursor.lastrowid
            
            subtasks = generate_subtasks(main_task_content)
            for subtask_content in subtasks:
                cursor.execute("INSERT INTO subtasks (content, task_id) VALUES (?, ?)", (subtask_content, new_task_id))
            
            conn.commit()
            conn.close()
            # NEW: Flash a success message
            flash('🚀 Task added and broken down by AI!', 'success')
        else:
            flash('Task content cannot be empty.', 'error')
        return redirect(url_for('index'))

    else: # GET request
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks ORDER BY id DESC")
        tasks = cursor.fetchall()
        
        tasks_with_subtasks = []
        for task in tasks:
            cursor.execute("SELECT * FROM subtasks WHERE task_id = ?", (task['id'],))
            subtasks = cursor.fetchall()
            tasks_with_subtasks.append({'task': task, 'subtasks': subtasks})
            
        conn.close()
        return render_template('index.html', tasks_with_subtasks=tasks_with_subtasks)

# NEW: Route to mark a task as complete
@app.route('/complete/<int:task_id>')
def complete_task(task_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = 'complete' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    flash('✅ Task marked as complete!', 'success')
    return redirect(url_for('index'))

@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subtasks WHERE task_id = ?", (task_id,))
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    flash('🗑️ Task successfully deleted!', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)