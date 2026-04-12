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
        database_url = os.getenv('DATABASE_URL')
        # Safety check: ensures the URL uses the correct driver name
        if database_url and database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(database_url)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def get_user_status(name):
    # Change '?' to '%s' here because query_db handles the conversion based on IS_RENDER
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

import uuid # Add this to your imports at the top!

@app.route('/detect_face', methods=['POST'])
def detect_face():
    data = request.json
    name = data.get("name")
    confidence = data.get("confidence", 0)
    image_data = data.get("image_data") # This is the Base64 string

    if name == "Unknown" and image_data:
        # Create a unique temp ID using current time
        temp_id = f"UKN_{int(time.time())}"
        
        # Insert into Unknowns Table
        # If testing on SQLite, make sure your init_db.py has created this table!
        try:
            query_db("""
                INSERT INTO unknown_subjects (temp_id, last_image_path, capture_count)
                VALUES (?, ?, 1)
            """, (temp_id, image_data))
            print(f"🚨 ALERT: Unknown subject {temp_id} registered.")
        except Exception as e:
            print(f"❌ DB Error (Unknown): {e}")
            
    else:
        # Standard Log for Known Personnel
        query_db("INSERT INTO logs (name, status, confidence) VALUES (?, 'ENTRY', ?)", 
                 (name, confidence))

    return jsonify({"status": "success"}), 200


def query_db(query, args=(), one=False):
    conn = get_db()
    
    try:
        # Use RealDictCursor for Postgres, or a simple cursor for SQLite
        if IS_RENDER:
            query = query.replace('?', '%s')
            cur = conn.cursor(cursor_factory=RealDictCursor)
        else:
            cur = conn.cursor()
            
        cur.execute(query, args)
        
        # Check if the query is a SELECT to fetch data
        if query.strip().upper().startswith("SELECT"):
            rv = cur.fetchall()
            # If SQLite, convert row objects to dictionaries so they match Postgres behavior
            if not IS_RENDER and rv:
                rv = [dict(row) for row in rv]
        else:
            conn.commit()
            rv = None
            
        return (rv[0] if rv else None) if one else rv
    except Exception as e:
        print(f"❌ Database Error: {e}")
        return None
    finally:
        conn.close()


@app.route("/test_db")
def test_db():
    try:
        # Try to fetch one row from the new table
        res = query_db("SELECT * FROM unknown_subjects LIMIT 1")
        return jsonify({"status": "Table exists!", "data": str(res)})
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500
    
         
# ---------------- EXIT LOGIC ----------------
@app.route('/exit_user', methods=['POST'])
def exit_user():
    try:
        data = request.get_json()
        name = data.get('name', 'Unknown') # Default to Unknown if name is missing

        if cooldown.can_log(name, "EXIT"):
            log_to_db(name, "EXIT", "", 0.0)
            return jsonify({"status": "success", "message": f"Exit logged for {name}"})
        
        return jsonify({"status": "skipped"})
    except Exception as e:
        return jsonify({"status": "error", "reason": str(e)}), 500


@app.route("/register", methods=["GET", "POST"])
def register():
    # Only Owners and HR should be able to register new people
    current_role = session.get("role", "").lower()
    if current_role not in ["owner", "hr"]:
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        username = request.form.get("username")
        name = request.form.get("name")
        password = request.form.get("password")
        role = request.form.get("role")
        face_image = request.files.get("face_image")

        if not face_image:
            flash("Face image is required for enrollment.", "error")
            return redirect(request.url)

        # 1. Save the Image to the dataset folder
        # We name the file after the 'name' variable so the AI knows who it is
        filename = f"{name.replace(' ', '_').lower()}.jpg"
        image_path = os.path.join(DATASET_FOLDER, filename)
        face_image.save(image_path)

        # 2. Save User to Database
        try:
            query_db("""
                INSERT INTO users (username, name, password, role, status) 
                VALUES (?, ?, ?, ?, 'active')
            """, (username, name, password, role))
            
            flash(f"Identity for {name} created successfully!", "success")
            return redirect(url_for("hr"))
        except Exception as e:
            flash(f"Database Error: {str(e)}", "error")
            return redirect(request.url)

    return render_template("register.html", current_user_role=current_role)


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

@app.route("/unknowns")
def view_unknowns():
    # Security Check: Only Owner and HR can access the intelligence gallery
    if session.get("role") not in ["owner", "security"]: 
        return redirect(url_for("login"))
    
    # We fetch all data from the unknown_subjects table
    # and pass it to the template as 'unknown_list'
    data = query_db("SELECT * FROM unknown_subjects ORDER BY last_seen DESC")
    
    return render_template("unknowns.html", unknown_list=data)

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
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=False)