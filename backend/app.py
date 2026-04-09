from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
import sqlite3
import os
import base64
import cv2
import sys
from datetime import datetime
from dotenv import load_dotenv
import psycopg2 # ADD THIS
from psycopg2.extras import RealDictCursor
from backend.database.db_logger import log_to_db
from backend.utils.cooldown import CooldownManager

# 1. Load environment variables
load_dotenv() 

# 2. Initialize Flask App
# Note: We keep static_folder as 'static' so Flask can serve CSS/JS easily
app = Flask(__name__, template_folder='templates', static_folder='static')

# 3. Security
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'sentricore_key_dev')

# 4. PATH CONFIGURATION (Logic for Local vs Render)
IS_RENDER = os.getenv('RENDER')
current_dir = os.path.dirname(os.path.abspath(__file__))

if IS_RENDER:
    # --- PROD: Render Persistent Disk ---
    BASE_DATA_DIR = "/opt/render/project/src/data"
    DB_PATH = os.path.join(BASE_DATA_DIR, "attendance.db")
    # We store images in the persistent disk, but we'll need a way to serve them
    UNKNOWN_FOLDER = os.path.join(BASE_DATA_DIR, "unknown_faces")
    DATASET_FOLDER = os.path.join(BASE_DATA_DIR, "dataset")
else:
    # --- DEV: Local Windows ---
    DB_PATH = os.path.join(current_dir, "database", "attendance.db")
    UNKNOWN_FOLDER = os.path.join(current_dir, "static", "unknown_faces")
    DATASET_FOLDER = os.path.join(os.path.dirname(current_dir), "dataset")

# Ensure persistent folders exist
for folder in [UNKNOWN_FOLDER, DATASET_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# 5. Handle System Path for backend modules
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.database.db_logger import log_to_db
from backend.utils.cooldown import CooldownManager

cooldown = CooldownManager(15)

# ---------------- DATABASE HELPERS ----------------
def get_db():
    if IS_RENDER:
        # Connect to Postgres using the URL you put in Environment Variables
        database_url = os.getenv('DATABASE_URL')
        conn = psycopg2.connect(database_url)
        # RealDictCursor makes Postgres act like sqlite3.Row
        return conn
    else:
        # Use your local SQLite for development
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def get_user_status(name):
    user = query_db("SELECT status FROM users WHERE name=?", (name,), one=True)
    return user['status'] if user else "unknown"
# ---------------- SERVING PERSISTENT IMAGES ----------------
# Since Render's persistent disk is outside the 'static' folder, 
# we need this route to show unknown faces on the web page.
@app.route('/media/unknown/<filename>')
def serve_unknown(filename):
    from flask import send_from_directory
    return send_from_directory(UNKNOWN_FOLDER, filename)

# ---------------- ROUTES ----------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/detect_face', methods=['POST'])
def detect_face():
    """
    RECEIVES DATA FROM LAPTOP.
    Laptop does the Face Recognition and sends just the Name and Confidence.
    """
    try:
        data = request.get_json()
        name = data.get('name', 'Unknown')
        confidence = float(data.get('confidence', 0.0))

        if name == "Unknown":
            if cooldown.can_log("Unknown", "ALERT"):
                log_to_db("Unknown", "ALERT", "", confidence)
        else:
            status = get_user_status(name)
            action = "ENTRY" if status == "active" else "ALERT"
            if cooldown.can_log(name, action):
                log_to_db(name, action, "", confidence)

        return jsonify({"status": "success", "logged": name})
    except Exception as e:
        print(f"Logging Error: {e}")
        return jsonify({"status": "error"}), 500
    

def index():
    return render_template("index.html")



def query_db(query, args=(), one=False):
    conn = get_db()
    
    # Smart Placeholder: Automatically swap ? for %s if on Render
    if IS_RENDER:
        query = query.replace('?', '%s')
        cur = conn.cursor(cursor_factory=RealDictCursor)
    else:
        cur = conn.cursor()
        
    try:
        cur.execute(query, args)
        
        # If it's a SELECT, fetch data
        if query.strip().upper().startswith("SELECT"):
            rv = cur.fetchall()
        else:
            # For INSERT/UPDATE/DELETE, commit and return nothing
            conn.commit()
            rv = None
            
        return (rv[0] if rv else None) if one else rv
    except Exception as e:
        print(f"Database Error: {e}")
        return None
    finally:
        conn.close()

# ---------------- EXIT LOGIC ----------------
@app.route('/exit_user', methods=['POST'])
def exit_user():
    """Endpoint for the local laptop to report when a user leaves the frame."""
    try:
        data = request.get_json()
        name = data.get('name')

        if not name:
            return jsonify({"status": "error", "message": "No name provided"}), 400

        # Optional: Use a short cooldown so we don't log 'EXIT' 
        # if they just blinked out for 1 second.
        if cooldown.can_log(name, "EXIT"):
            log_to_db(name, "EXIT", "", 0.0)
            print(f"🚪 Logged EXIT for {name}")
            return jsonify({"status": "success", "message": f"Exit logged for {name}"})
        
        return jsonify({"status": "skipped", "message": "Cooldown active"})
        
    except Exception as e:
        print(f"Error in exit_user: {e}")
        return jsonify({"status": "error"}), 500
    

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = query_db("SELECT * FROM users WHERE username=? AND password=? AND status='active'", 
                        (username, password), one=True)
        if user:
            session["user"] = user["username"]
            session["role"] = user["role"]
            
            # Redirect based on role
            role = str(user["role"]).strip().lower()
            if role == "owner": return redirect(url_for("owner"))
            if role == "hr": return redirect(url_for("hr"))
            return redirect(url_for("logs"))
            
        flash("Authentication Failed", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/owner")
def owner():
    if session.get("role") != "owner": return redirect(url_for("login"))
    
    # Simple count queries
    res_total = query_db("SELECT COUNT(*) as count FROM users", one=True)
    res_active = query_db("SELECT COUNT(*) as count FROM users WHERE status = 'active'", one=True)
    
    total = res_total['count'] if res_total else 0
    active = res_active['count'] if res_active else 0
    
    return render_template("owner.html", total_users=total, active_users=active)


@app.route("/logs")
def logs():
    # Show last 50 events
    logs_data = query_db("SELECT * FROM logs ORDER BY id DESC LIMIT 50")
    return render_template("index_logs.html", logs=logs_data)

@app.route("/hr")
def hr():
    if session.get("role") not in ["owner", "hr"]: return redirect(url_for("login"))
    users_data = query_db("SELECT * FROM users")
    return render_template("hr.html", users=users_data)


@app.route("/update_user/<int:user_id>", methods=["GET", "POST"])
def update_user(user_id):
    current_role = session.get("role", "").lower()
    if current_role not in ["owner", "hr"]: return redirect(url_for("login"))

    target_user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not target_user: return redirect(url_for("hr"))

    if request.method == "POST":
        name = request.form.get("name")
        new_password = request.form.get("password")
        status = request.form.get("status")
        role = request.form.get("role").lower()

        if new_password:
            query_db("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))

        query_db("UPDATE users SET name=?, role=?, status=? WHERE id=?", (name, role, status, user_id))
        
        flash("Profile updated successfully!", "success")
        return redirect(url_for("hr"))

    return render_template("edit_user.html", user=target_user, current_role=current_role)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)