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

# --- PATH FIX FOR IMPORTS ---
# This allows app.py to find backend.database and backend.utils
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.database.db_logger import log_to_db
from backend.utils.cooldown import CooldownManager

app = Flask(__name__, 
            template_folder='templates', 
            static_folder='static')
app.secret_key = "sentricore_key"

# --- ABSOLUTE PATH CONFIGURATION ---
DB_PATH = os.path.join(current_dir, "database", "attendance.db")
UNKNOWN_FOLDER = os.path.join(current_dir, "static", "unknown_faces")
UPLOAD_FOLDER = os.path.join(current_dir, "static", "uploads")

app.config['UNKNOWN_FOLDER'] = UNKNOWN_FOLDER
cooldown = CooldownManager(15)

# Ensure folders exist
for folder in [UNKNOWN_FOLDER, UPLOAD_FOLDER]:
    os.makedirs(folder, exist_ok=True)

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

        # --- LOGGING LOGIC ---
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

# 1. Define the Mapping at the top of your file
# The KEY is the role in your DB, the VALUE is the function name in app.py
REDIRECT_MAP = {
    "owner": "owner",
    "hr": "hr",
    "security": "logs"
}

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Match these names with your HTML 'name' attributes
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db()
        # Ensure we only fetch active users
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=? AND status='active'",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            # Create the session (your digital ID card)
            session["user"] = user["username"]
            session["role"] = user["role"]

            # 2. PERFORM THE ROLE-BASED REDIRECT
            # We strip() and lower() to prevent errors from accidental spaces or caps in the DB
            user_role = str(user["role"]).strip().lower()
            
            # Lookup the function name. If role isn't in our map, go to 'index'
            target_function = REDIRECT_MAP.get(user_role, "index")
            
            return redirect(url_for(target_function))

        # If user is None (wrong credentials)
        flash("Authentication Failed: Invalid Credentials", "error")

    return render_template("login.html")

@app.route("/logout")
def logout():
    # 1. Clear all data from the session
    session.clear()
    
    # 2. Add a friendly departure message
    flash("Session terminated. You have been logged out safely.", "success")
    
    # 3. Redirect to the home or login page
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    role = session.get("role")
    if role == "owner":
        return redirect(url_for("owner"))
    elif role == "hr":
        return redirect(url_for("hr")) # Or a specific HR home page if you have one
    else:
        # Default for employees/security
        return redirect(url_for("index"))


@app.route("/owner") # This is the URL in the browser address bar
def owner():         # This is the "endpoint" name used by url_for()
    # Security Check
    if session.get("role") != "owner":
        flash("Access Denied.", "error")
        return redirect(url_for("login"))

    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_users = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'active'").fetchone()[0]
    conn.close()

    # You can still keep the HTML file named "owner_dashboard.html" 
    # or rename it to "owner.html" if you prefer.
    return render_template("owner.html", 
                           total_users=total_users, 
                           active_users=active_users)
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


@app.route("/register", methods=["GET", "POST"])
def register():
    # 1. Get the role of the person currently logged in (the HR or Owner)
    # This assumes you stored it in the session during login
    current_user_role = session.get("role") 

    if request.method == "POST":
        new_user_role = request.form.get("role")
        
        # SECURITY CHECK: Prevent an HR user from "hacking" the form 
        # by manually sending 'owner' in the POST data.
        if new_user_role == "owner" and current_user_role != "owner":
            flash("Unauthorized action: Only Owners can create other Owners.", "danger")
            return redirect(url_for("register"))

        # ... proceed with database logic ...
        username = request.form.get("username")
        # db.insert(...)
        
        flash(f"Identity for {username} enrolled successfully.", "success")
        return redirect(url_for("hr"))

    # 2. Pass 'current_user_role' to the template
    return render_template("register.html", current_user_role=current_user_role)

@app.route("/update_user/<int:user_id>", methods=["GET", "POST"])
def update_user(user_id):
    # Security Check: Ensure the person accessing this is at least HR or Owner
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
        # 1. SECURITY GUARD: HR cannot modify an existing Owner account
        target_role = target_user["role"].lower()
        if current_role == "hr" and target_role == "owner":
            conn.close()
            flash("Permission Denied: HR cannot modify Owner profiles.", "error")
            return redirect(url_for("hr"))

        # 2. ROLE ESCALATION GUARD: Only an Owner can assign the "Owner" role
        new_requested_role = request.form.get("role").lower()
        if new_requested_role == "owner" and current_role != "owner":
            conn.close()
            flash("Permission Denied: Only the system Owner can grant Owner status.", "error")
            return redirect(url_for("hr"))

        name = request.form.get("name")
        new_password = request.form.get("password")
        status = request.form.get("status")

        # Handle Password
        if new_password and new_password.strip() != "":
            conn.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))

        # Handle Image
        file = request.files.get("face_image")
        if file and file.filename != '':
            filename = f"{target_user['username']}.jpg"
            file.save(os.path.join("dataset", filename))

        # Update core profile (using the new_requested_role checked above)
        conn.execute(
            "UPDATE users SET name = ?, role = ?, status = ? WHERE id = ?",
            (name, new_requested_role, status, user_id)
        )
        conn.commit()
        conn.close()

        flash(f"Profile updated successfully!", "success")
        return redirect(url_for("hr"))

    # GET Request Logic
    conn.close()
    return render_template("edit_user.html", user=target_user, current_role=current_role)

if __name__ == "__main__":
    app.run(debug=False)