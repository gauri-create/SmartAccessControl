from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import numpy as np
import face_recognition 
import cv2
import os


app = Flask(__name__)

app.secret_key = "sentricore_key"

DB = "backend/database/attendance.db"

# ---------------- DB CONNECTION ----------------
def get_db():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys = ON;") 
    return conn

# ---------------- ACCESS CONTROL ----------------
def has_access(role, allowed_roles):
    return role in (allowed_roles if isinstance(allowed_roles, list) else [allowed_roles])

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=? AND status='active'",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["user"] = user["username"]
            session["role"] = user["role"].lower()
            
            role = session["role"]
            if role == "security":
                return redirect("/logs")
            elif role == "hr":
                return redirect("/hr")
            elif role == "owner":
                return redirect("/owner")
            
        return "Invalid Credentials"
    return render_template("login.html")

# ---------------- OWNER (THE MISSING ROUTE) ----------------
@app.route("/owner")
def owner():
    role = session.get("role")
    if role != "owner":
        return "Access Denied: Owner only"
    return render_template("owner.html")

# ---------------- HR PANEL ----------------
@app.route("/hr")
def hr():
    if not has_access(session.get("role"), ["hr", "owner"]): 
        return "Access Denied"
    conn = get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return render_template("hr.html", users=users)

# ---------------- LOGS ----------------
@app.route("/logs")
def logs():
    if not has_access(session.get("role"), ["security", "owner"]):
        return "Access Denied"
    conn = get_db()
    db_logs = conn.execute("SELECT * FROM logs ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("index_logs.html", logs=db_logs)

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if not has_access(session.get("role"), ["hr", "owner"]):
        return "Access Denied"

    if request.method == "POST":
        username = request.form["username"].strip().lower()
        name = request.form["name"].strip()
        password = request.form["password"]
        user_role = request.form["role"].strip().lower()
        file = request.files.get('face_image')

        if not file: return "Face image required"

        image = face_recognition.load_image_file(file)
        encodings = face_recognition.face_encodings(image)

        if len(encodings) == 0: return "No face detected"

        binary_encoding = encodings[0].tobytes()

        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, name, password, role, status) VALUES (?, ?, ?, ?, 'active')",
                        (username, name, password, user_role))
            user_id = cur.lastrowid
            cur.execute("INSERT INTO face_data (user_id, encoding) VALUES (?, ?)", (user_id, binary_encoding))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Username exists"
        finally:
            conn.close()
        return redirect("/hr")
    return render_template("register.html")

# ---------------- UPDATE & TOGGLE ----------------
@app.route("/update_user/<int:user_id>", methods=["GET", "POST"])
def update_user(user_id):
    current_role = session.get("role")
    if not has_access(current_role, ["hr", "owner"]): return "Access Denied", 403
    
    conn = get_db()
    target_user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    
    if not target_user:
        conn.close()
        return "User not found", 404

    if target_user["role"] == "owner" and current_role != "owner":
        conn.close()
        return "Access Denied", 403
    
    if request.method == "POST":
        new_name = request.form["name"].strip()
        new_role = request.form["role"].strip().lower()
        new_status = request.form["status"].strip().lower()
        new_password = request.form["password"].strip()
        file = request.files.get('face_image')

        # Prevent HR from changing roles to 'owner'
        final_role = new_role if current_role == "owner" else target_user["role"]

        # 1. Update Basic Info
        conn.execute("UPDATE users SET name=?, role=?, status=? WHERE id=?", 
                     (new_name, final_role, new_status, user_id))

        # 2. Update Password if provided
        if new_password:
            conn.execute("UPDATE users SET password=? WHERE id=?", (new_password, user_id))

        # 3. Update Face Image if provided
        if file and file.filename != '':
            image = face_recognition.load_image_file(file)
            encodings = face_recognition.face_encodings(image)
            
            if len(encodings) > 0:
                binary_encoding = encodings[0].tobytes()
                # Check if face_data exists, then update or insert
                conn.execute("INSERT OR REPLACE INTO face_data (user_id, encoding) VALUES (?, ?)", 
                             (user_id, binary_encoding))
            else:
                return "No face detected in the new image. Update failed.", 400

        conn.commit()
        conn.close()
        return redirect("/hr")
    
    conn.close()
    return render_template("edit_user.html", user=target_user)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
import os

if __name__ == "__main__":
    # Get port from environment variable, default to 5000 for local testing
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)