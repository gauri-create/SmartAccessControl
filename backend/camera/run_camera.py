import cv2
import face_recognition
import numpy as np
import sqlite3
import time
import os

from datetime import datetime
from backend.database.db_logger import log_to_db
from backend.utils.cooldown import CooldownManager



DB_PATH = "backend/database/attendance.db"

cooldown = CooldownManager(15)
active_users = {}


def save_snapshot(frame, name):
    folder = "backend/static/captures"

    if name == "Unknown":
        folder = "backend/static/unknown_faces"

    os.makedirs(folder, exist_ok=True)

    filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    path = os.path.join(folder, filename)

    cv2.imwrite(path, frame)

    return f"captures/{filename}" if name != "Unknown" else f"unknown_faces/{filename}"

def load_faces():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name, encoding FROM face_data")
    rows = cursor.fetchall()

    conn.close()

    encodings = []
    names = []

    for name, enc in rows:
        encodings.append(np.frombuffer(enc, dtype=np.float64))
        names.append(name)

    return encodings, names


known_encodings, known_names = load_faces()


def get_status(name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT access_status FROM users WHERE name=?", (name,))
    row = cursor.fetchone()

    conn.close()
    return row[0] if row else "unknown"


video = cv2.VideoCapture(0)

while True:
    ret, frame = video.read()
    if not ret:
        break

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    locations = face_recognition.face_locations(rgb)
    encodings = face_recognition.face_encodings(rgb, locations)

    for face_encoding, loc in zip(encodings, locations):

        matches = face_recognition.compare_faces(known_encodings, face_encoding)
        name = "Unknown"

        if True in matches:
            name = known_names[matches.index(True)]

        # 🔴 UNKNOWN
        if name == "Unknown":
            if cooldown.can_log("Unknown", "ALERT"):
                file = save_snapshot(frame, "Unknown")
                log_to_db("Unknown", "ALERT", file)
            continue

        status = get_status(name)

        # 🔴 INACTIVE
        if status == "inactive":
            if cooldown.can_log(name, "ALERT"):
                file = save_snapshot(frame, name)
                log_to_db(name, "ALERT", file)
            continue

        # 🟢 ACTIVE ENTRY
        if name not in active_users:
            file = save_snapshot(frame, name)
            log_to_db(name, "ENTRY", file)
            active_users[name] = time.time()

        else:
            active_users[name] = time.time()

    # EXIT
    now = time.time()
    for user in list(active_users.keys()):
        if now - active_users[user] > 10:
            log_to_db(user, "EXIT", "")
            del active_users[user]

    cv2.imshow("Camera", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

video.release()
cv2.destroyAllWindows()