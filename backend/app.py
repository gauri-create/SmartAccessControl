from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
import sqlite3
import numpy as np
import face_recognition
import os
import base64
import cv2
import pickle
import sys
from datetime import datetime
from dotenv import load_dotenv

# 1. Load environment variables
load_dotenv() 

# 2. Initialize Flask App
app = Flask(__name__, template_folder='templates', static_folder='static')

# 3. Security: Pull Secret Key from Environment
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'sentricore_key_dev')

# 4. PATH CONFIGURATION (Logic for Local vs Render)
IS_RENDER = os.getenv('RENDER')

# This helps find your backend modules
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

if IS_RENDER:
    # --- PROD: Render Persistent Disk Paths ---
    BASE_DATA_DIR = "/opt/render/project/src/data"
    DB_PATH = os.path.join(BASE_DATA_DIR, "attendance.db")
    UNKNOWN_FOLDER = os.path.join(BASE_DATA_DIR, "static", "unknown_faces")
    UPLOAD_FOLDER = os.path.join(BASE_DATA_DIR, "static", "uploads")
    DATASET_FOLDER = os.path.join(BASE_DATA_DIR, "dataset")
else:
    # --- DEV: Local Windows Paths ---
    DB_PATH = os.path.join(current_dir, "database", "attendance.db")
    UNKNOWN_FOLDER = os.path.join(current_dir, "static", "unknown_faces")
    UPLOAD_FOLDER = os.path.join(current_dir, "static", "uploads")
    # Assuming dataset is in the root folder
    DATASET_FOLDER = os.path.join(os.path.dirname(current_dir), "dataset")

app.config['UNKNOWN_FOLDER'] = UNKNOWN_FOLDER

# Ensure all folders exist
for folder in [UNKNOWN_FOLDER, UPLOAD_FOLDER, DATASET_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# 5. Imports from your custom modules
from backend.database.db_logger import log_to_db
from backend.utils.cooldown import CooldownManager

cooldown = CooldownManager(15)

# ---------------- DATABASE HELPERS ----------------
def get_db():
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

reload_known_faces()

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
                filepath = os.path.join(app.config['UNKNOWN_FOLDER'], filename)
                cv2.imwrite(filepath, frame)
                log_to_db("Unknown", "ALERT", f"unknown_faces/{filename}", confidence)
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

REDIRECT_MAP = {
    "owner": "owner",
    "hr": "hr",
    "security": "logs"
}

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=? AND status='active'",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["user"] = user["username"]
            session["role"] = user["role"]
            user_role = str(user["role"]).strip().lower()
            target_function = REDIRECT_MAP.get(user_role, "index")
            return redirect(url_for(target_function))

        flash("Authentication Failed: Invalid Credentials", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Session terminated. You have been logged out safely.", "success")
    return redirect(url_for("login"))

@app.route("/owner")
def owner():
    if session.get("role") != "owner":
        flash("Access Denied.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_users = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'active'").fetchone()[0]
    conn.close()
    return render_template("owner.html", total_users=total_users, active_users=active_users)

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
    if current_role not in ["owner", "hr"]:
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    target_user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    if not target_user:
        conn.close()
        flash("User not found.", "error")
        return redirect(url_for("hr"))

    if request.method == "POST":
        target_role = target_user["role"].lower()
        if current_role == "hr" and target_role == "owner":
            conn.close()
            flash("Permission Denied: HR cannot modify Owner profiles.", "error")
            return redirect(url_for("hr"))

        name = request.form.get("name")
        new_password = request.form.get("password")
        status = request.form.get("status")
        new_requested_role = request.form.get("role").lower()

        if new_password and new_password.strip() != "":
            conn.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))

        file = request.files.get("face_image")
        if file and file.filename != '':
            filename = f"{target_user['username']}.jpg"
            file.save(os.path.join(DATASET_FOLDER, filename))

        conn.execute(
            "UPDATE users SET name = ?, role = ?, status = ? WHERE id = ?",
            (name, new_requested_role, status, user_id)
        )
        conn.commit()
        conn.close()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("hr"))

    conn.close()
    return render_template("edit_user.html", user=target_user, current_role=current_role)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)