from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
import sqlite3
import numpy as np
import face_recognition
import os
import base64
import cv2
import sys
from datetime import datetime
from dotenv import load_dotenv
import psycopg2 # ADD THIS
from psycopg2.extras import RealDictCursor

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
    conn = get_db()
    user = conn.execute("SELECT status FROM users WHERE name=?", (name,)).fetchone()
    conn.close()
    return user['status'] if user else "unknown"

# ---------------- FACE DATA LOADING ----------------
known_face_encodings = []
known_face_names = []

def reload_known_faces():
    global known_face_encodings, known_face_names
    try:
        conn = get_db()
        data = conn.execute("""
            SELECT users.name, face_data.encoding 
            FROM users 
            JOIN face_data ON users.id = face_data.user_id 
            WHERE users.status = 'active'
        """).fetchall()
        conn.close()

        known_face_encodings = [np.frombuffer(row['encoding'], dtype=np.float64) for row in data]
        known_face_names = [row['name'] for row in data]
        print(f"✅ Loaded {len(known_face_names)} faces.")
    except Exception as e:
        print(f"❌ Load error: {e}")

# Initial load
reload_known_faces()

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
    try:
        data = request.get_json()
        image_b64 = data.get('image').split(",")[1]
        image_bytes = base64.b64decode(image_b64)
        
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        name = "Unknown"
        confidence = 0.0

        if face_encodings:
            matches = face_recognition.compare_faces(known_face_encodings, face_encodings[0], tolerance=0.5)
            face_distances = face_recognition.face_distance(known_face_encodings, face_encodings[0])

            if len(face_distances) > 0 and True in matches:
                best_match_index = np.argmin(face_distances)
                name = known_face_names[best_match_index]
                confidence = float(1 - face_distances[best_match_index])

        if name == "Unknown":
            if cooldown.can_log("Unknown", "ALERT"):
                filename = f"web_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                filepath = os.path.join(UNKNOWN_FOLDER, filename)
                cv2.imwrite(filepath, frame)
                # Save the URL path so the <img> tag can find it
                img_url = url_for('serve_unknown', filename=filename)
                log_to_db("Unknown", "ALERT", img_url, confidence)
        else:
            status = get_user_status(name)
            if status == "active":
                if cooldown.can_log(name, "ENTRY"):
                    log_to_db(name, "ENTRY", "", confidence)
            else:
                if cooldown.can_log(name, "ALERT"):
                    log_to_db(name, "ALERT", "", confidence)

        return jsonify({"status": "success", "detected": name})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error"}), 500

REDIRECT_MAP = {"owner": "owner", "hr": "hr", "security": "logs"}


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
        
        # Using query_db makes this work on both SQLite and Postgres!
        user = query_db("SELECT * FROM users WHERE username=? AND password=? AND status='active'", 
                        (username, password), one=True)

        if user:
            session["user"] = user["username"]
            session["role"] = user["role"]
            target = REDIRECT_MAP.get(str(user["role"]).strip().lower(), "index")
            return redirect(url_for(target))
        flash("Authentication Failed", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/owner")
def owner():
    if session.get("role") != "owner": return redirect(url_for("login"))
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'active'").fetchone()[0]
    conn.close()
    return render_template("owner.html", total_users=total, active_users=active)

@app.route("/logs")
def logs():
    conn = get_db()
    logs_data = conn.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return render_template("index_logs.html", logs=logs_data)

@app.route("/hr")
def hr():
    conn = get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return render_template("hr.html", users=users)

@app.route("/update_user/<int:user_id>", methods=["GET", "POST"])
def update_user(user_id):
    current_role = session.get("role", "").lower()
    if current_role not in ["owner", "hr"]: return redirect(url_for("login"))

    conn = get_db()
    target_user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target_user:
        conn.close()
        return redirect(url_for("hr"))

    if request.method == "POST":
        name = request.form.get("name")
        new_password = request.form.get("password")
        status = request.form.get("status")
        role = request.form.get("role").lower()

        if new_password:
            conn.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))

        file = request.files.get("face_image")
        if file and file.filename != '':
            filename = f"{target_user['username']}.jpg"
            file.save(os.path.join(DATASET_FOLDER, filename))

        conn.execute("UPDATE users SET name=?, role=?, status=? WHERE id=?", (name, role, status, user_id))
        conn.commit()
        conn.close()
        
        # REFRESH face encodings so the camera recognizes changes immediately
        reload_known_faces()
        
        flash("Profile updated successfully!", "success")
        return redirect(url_for("hr"))

    conn.close()
    return render_template("edit_user.html", user=target_user, current_role=current_role)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)