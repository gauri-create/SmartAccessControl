from flask import Flask, render_template, request, jsonify
import sqlite3
import os
from werkzeug.utils import secure_filename
import face_recognition
import numpy as np

app = Flask(__name__)

DB_PATH = "backend/database/attendance.db"
UPLOAD_FOLDER = "backend/static/known_faces"

# ---------------- DATABASE ----------------
def get_connection():
    return sqlite3.connect(DB_PATH)


# ---------------- UTIL ----------------
def get_latest_unknown():
    folder = "backend/static/unknown_faces"

    if not os.path.exists(folder):
        return None

    files = os.listdir(folder)
    if not files:
        return None

    files.sort(reverse=True)
    return files[0]


# ---------------- ROUTES ----------------
@app.route("/")
def index():
    name = request.args.get("name", "")
    status = request.args.get("status", "")

    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT name, status, timestamp, image FROM logs WHERE 1=1"
    params = []

    # Filter: Name
    if name:
        query += " AND LOWER(name) LIKE LOWER(?)"
        params.append(f"%{name}%")

    # Filter: Status
    if status:
        query += " AND LOWER(status) = LOWER(?)"
        params.append(status)

    query += " ORDER BY timestamp DESC"

    cursor.execute(query, params)
    logs = cursor.fetchall()

    conn.close()

    latest_unknown = get_latest_unknown()

    return render_template(
        "index.html",
        logs=logs,
        latest_unknown=latest_unknown
    )


@app.route("/api/logs")
def api_logs():
    name = request.args.get("name", "")
    status = request.args.get("status", "")

    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT name, status, timestamp, image FROM logs WHERE 1=1"
    params = []

    if name:
        query += " AND LOWER(name) LIKE LOWER(?)"
        params.append(f"%{name}%")

    if status:
        query += " AND LOWER(status) = LOWER(?)"
        params.append(status)

    query += " ORDER BY id DESC LIMIT 50"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    conn.close()

    data = [
        {
            "name": r[0],
            "status": r[1],
            "timestamp": r[2],
            "image": r[3]
        }
        for r in rows
    ]

    return jsonify(data)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        file = request.files["image"]

        if not name or not file:
            return "Missing data"

        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file.save(path)

        # generate encoding
        image = face_recognition.load_image_file(path)
        encodings = face_recognition.face_encodings(image)

        if len(encodings) == 0:
            return "No face detected"

        new_encoding = encodings[0]

        # convert encoding to bytes
        encoding_bytes = new_encoding.tobytes()

        # store in DB
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO users (name, image, encoding)
            VALUES (?, ?, ?)
        """, (name, filename, encoding_bytes))

        conn.commit()
        conn.close()

        return "User Registered Successfully"

    return render_template("register.html")

# ---------------- MAIN ----------------
if __name__ == "__main__":
    app.run(debug=True)