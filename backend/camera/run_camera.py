import cv2
import face_recognition
import numpy as np
import sqlite3
import time
import os
from datetime import datetime
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from backend.database.db_logger import log_to_db
from backend.utils.cooldown import CooldownManager

DB_PATH = "backend/database/attendance.db"
UNKNOWN_FOLDER = "backend/static/unknown_faces"

cooldown = CooldownManager(15)
active_users = {}

def save_unknown_snapshot(frame):
    """Saves image ONLY for unknown intruders."""
    os.makedirs(UNKNOWN_FOLDER, exist_ok=True)
    filename = f"Unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    path = os.path.join(UNKNOWN_FOLDER, filename)
    cv2.imwrite(path, frame)
    return f"unknown_faces/{filename}"

def load_faces():
    """Loads encodings from the new BLOB-based face_data table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Note the join: we get the name from the users table via user_id
    cursor.execute("""
        SELECT users.name, face_data.encoding 
        FROM face_data 
        JOIN users ON face_data.user_id = users.id
    """)
    rows = cursor.fetchall()
    conn.close()

    encodings = []
    names = []
    for name, enc in rows:
        encodings.append(np.frombuffer(enc, dtype=np.float64))
        names.append(name)
    return encodings, names

def get_status(name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM users WHERE name=?", (name,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "unknown"

# Initial Load
known_encodings, known_names = load_faces()
video = cv2.VideoCapture(0)
process_this_frame = True # For frame skipping (i3 optimization)

while True:
    ret, frame = video.read()
    if not ret: break

    # 1. Resize frame to 1/4 size for faster processing on i3
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    # 2. Only process every other frame to save CPU
    if process_this_frame:
        locations = face_recognition.face_locations(rgb_small_frame)
        encodings = face_recognition.face_encodings(rgb_small_frame, locations)

        for face_encoding, loc in zip(encodings, locations):
            matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.5)
            face_distances = face_recognition.face_distance(known_encodings, face_encoding)
            
            name = "Unknown"
            confidence = 0.0

            if len(face_distances) > 0 and True in matches:
                best_match_index = np.argmin(face_distances)
                name = known_names[best_match_index]
                confidence = 1 - face_distances[best_match_index]

            # --- LOGIC SEPARATION ---
            
            if name == "Unknown":
                if cooldown.can_log("Unknown", "ALERT"):
                    img_path = save_unknown_snapshot(frame)
                    log_to_db("Unknown", "ALERT", img_path, confidence)
                continue

            status = get_status(name)
            if status == "inactive":
                if cooldown.can_log(name, "ALERT"):
                    log_to_db(name, "ALERT", "", confidence) # No image needed for known blocked users
                continue

            # 🟢 Entry Logic (No Image Saved)
            if name not in active_users:
                log_to_db(name, "ENTRY", "", confidence)
                active_users[name] = time.time()
            else:
                active_users[name] = time.time()

    process_this_frame = not process_this_frame

    # EXIT TRACKER
    now = time.time()
    for user in list(active_users.keys()):
        if now - active_users[user] > 10:
            log_to_db(user, "EXIT", "", 0)
            del active_users[user]

    cv2.imshow("SentriCore Surveillance", frame)
    if cv2.waitKey(1) & 0xFF == 27: break

video.release()
cv2.destroyAllWindows()