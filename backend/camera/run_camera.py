import cv2
import face_recognition
import numpy as np
import sqlite3
import os
import time
from datetime import datetime

from backend.database.db_logger import log_to_db
from backend.utils.cooldown import CooldownManager

# ---------------- CONFIG ----------------
DB_PATH = "backend/database/attendance.db"
COOLDOWN_SECONDS = 15
FRAME_SKIP = 2

cooldown_manager = CooldownManager(cooldown_seconds=COOLDOWN_SECONDS)

active_users = {}
miss_counter = {}

frame_count = 0


# ---------------- LOAD FACES FROM DB ----------------
def load_known_faces():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name, encoding FROM users")
    rows = cursor.fetchall()

    conn.close()

    known_encodings = []
    known_names = []

    for name, enc_blob in rows:
        encoding = np.frombuffer(enc_blob, dtype=np.float64)
        known_encodings.append(encoding)
        known_names.append(name)

    return known_encodings, known_names


known_encodings, known_names = load_known_faces()


# ---------------- SNAPSHOT ----------------
def save_snapshot(frame, name):
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if name == "Unknown":
        folder = os.path.join(base_dir, "../static/unknown_faces")
    else:
        folder = os.path.join(base_dir, "../static/captures")

    os.makedirs(folder, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}.jpg"
    filepath = os.path.join(folder, filename)

    cv2.imwrite(filepath, frame)
    return filename


# ---------------- CAMERA ----------------
video = cv2.VideoCapture(0)

while True:
    ret, frame = video.read()
    if not ret:
        break

    frame_count += 1

    # skip frames for speed
    if frame_count % FRAME_SKIP != 0:
        cv2.imshow("Camera", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
        continue

    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb_small)
    face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

    detected_names = set()

    # ---------------- FACE MATCH ----------------
    for face_encoding, face_location in zip(face_encodings, face_locations):

        matches = face_recognition.compare_faces(known_encodings, face_encoding)
        face_distances = face_recognition.face_distance(known_encodings, face_encoding)

        name = "Unknown"

        if len(face_distances) > 0:
            best_match_index = np.argmin(face_distances)
            if matches[best_match_index]:
                name = known_names[best_match_index]

        # ---------------- KNOWN USER ----------------
        if name != "Unknown":
            detected_names.add(name)

            if name not in active_users:
                filename = save_snapshot(frame, name)
                log_to_db(name, "ENTRY", filename)

                active_users[name] = time.time()
                miss_counter[name] = 0
            else:
                active_users[name] = time.time()
                miss_counter[name] = 0

        # ---------------- UNKNOWN USER ----------------
        else:
            if cooldown_manager.can_log("Unknown", "ALERT"):
                filename = save_snapshot(frame, "Unknown")
                log_to_db("Unknown", "ALERT", filename)

        # ---------------- DRAW BOX ----------------
        top, right, bottom, left = [v * 4 for v in face_location]

        color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
        label = name if name != "Unknown" else "UNKNOWN"

        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.putText(frame, label, (left, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    # ---------------- EXIT LOGIC ----------------
    current_time = time.time()

    for user in list(active_users.keys()):

        if user not in detected_names:
            miss_counter[user] = miss_counter.get(user, 0) + 1
        else:
            miss_counter[user] = 0
            active_users[user] = current_time

        if current_time - active_users[user] > COOLDOWN_SECONDS:
            print(f"[EXIT] {user}")
            log_to_db(user, "EXIT", "no_image")

            del active_users[user]
            del miss_counter[user]

    # ---------------- SHOW FRAME ----------------
    cv2.imshow("Camera", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break


video.release()
cv2.destroyAllWindows()