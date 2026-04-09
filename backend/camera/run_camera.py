import cv2
import face_recognition
import numpy as np
import requests
import os
import time
import sqlite3

# --- CONFIGURATION ---
# Replace with your actual Render URL
CLOUD_BASE_URL = "https://your-app-name.onrender.com"
DETECT_URL = f"{CLOUD_BASE_URL}/detect_face"
EXIT_URL = f"{CLOUD_BASE_URL}/exit_user"

# Local DB Path (To load encodings from your laptop)
DB_PATH = os.path.join(os.path.dirname(__file__), "backend", "database", "attendance.db")

# Tracking users for Exit logic
active_users = {} 
known_face_encodings = []
known_face_names = []

def load_local_faces():
    """Loads encodings from your local SQLite DB in Nagpur."""
    global known_face_encodings, known_face_names
    print("🔄 Loading face database from local storage...")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        data = conn.execute("""
            SELECT users.name, face_data.encoding 
            FROM users 
            JOIN face_data ON users.id = face_data.user_id 
            WHERE users.status = 'active'
        """).fetchall()
        conn.close()

        known_face_encodings = [np.frombuffer(row['encoding'], dtype=np.float64) for row in data]
        known_face_names = [row['name'] for row in data]
        print(f"✅ Loaded {len(known_face_names)} faces locally.")
    except Exception as e:
        print(f"❌ Error loading faces: {e}")

def notify_cloud(name, confidence):
    """Sends the RECOGNIZED NAME to Render."""
    payload = {"name": name, "confidence": float(confidence)}
    try:
        response = requests.post(DETECT_URL, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"☁️ Cloud Synced: {name}")
    except Exception as e:
        print(f"📡 Cloud Sync Failed: {e}")

def notify_exit(name):
    """Sends EXIT event to Render."""
    try:
        requests.post(EXIT_URL, json={"name": name}, timeout=5)
        print(f"🚪 Cloud Exit Logged: {name}")
    except Exception as e:
        print(f"📡 Exit Sync Failed: {e}")

# --- START SYSTEM ---
load_local_faces()
video = cv2.VideoCapture(0)

print("--- SentriCore Edge Node Active ---")

while True:
    ret, frame = video.read()
    if not ret: break

    # 1. Faster processing: Resize and Convert
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    # 2. Recognition (Done LOCALLY on your i3)
    face_locations = face_recognition.face_locations(rgb_small_frame)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

    current_frame_names = []

    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.5)
        name = "Unknown"
        confidence = 0.0

        if True in matches:
            first_match_index = matches.index(True)
            name = known_face_names[first_match_index]
            face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
            confidence = 1 - face_distances[first_match_index]

        current_frame_names.append(name)

        # 3. Notify Cloud on discovery
        if name not in active_users:
            notify_cloud(name, confidence)
        
        active_users[name] = time.time()

    # 4. Exit Tracker (If not seen for 10 seconds)
    now = time.time()
    for user in list(active_users.keys()):
        if now - active_users[user] > 10:
            notify_exit(user)
            del active_users[user]

    # Visual Feedback
    cv2.putText(frame, "SentriCore Edge: Running Recognition", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.imshow("SentriCore Surveillance", frame)

    if cv2.waitKey(1) & 0xFF == 27: break

video.release()
cv2.destroyAllWindows()