import cv2
import face_recognition
import numpy as np
import requests
import os
import time
import sqlite3
import base64

# --- CONFIGURATION ---
CLOUD_BASE_URL = "http://127.0.0.1:5001"  # Switch to Render URL when deploying
DETECT_URL = f"{CLOUD_BASE_URL}/detect_face"
EXIT_URL = f"{CLOUD_BASE_URL}/exit_user"

# Local DB Path
DB_PATH = os.path.join(os.path.dirname(__file__), "backend", "database", "attendance.db")

active_users = {} 
known_face_encodings = []
known_face_names = []

def convert_frame_to_base64(frame):
    """Converts a CV2 image to a Base64 string for cloud storage."""
    _, buffer = cv2.imencode('.jpg', frame)
    return f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"

def load_local_faces():
    global known_face_encodings, known_face_names
    print("🔄 Loading face database...")
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
        print(f"✅ Loaded {len(known_face_names)} faces.")
    except Exception as e:
        print(f"❌ Load Error: {e}")

def notify_cloud(name, confidence, image_data=None):
    """Sends detection data to the backend."""
    payload = {
        "name": name, 
        "confidence": float(confidence),
        "image_data": image_data  # Only sent for Unknowns
    }
    try:
        requests.post(DETECT_URL, json=payload, timeout=5)
        print(f"☁️ Synced: {name}")
    except Exception as e:
        print(f"📡 Sync Failed: {e}")

# --- START SYSTEM ---
load_local_faces()
video = cv2.VideoCapture(0)

while True:
    ret, frame = video.read()
    if not ret: break

    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb_small_frame)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.5)
        name = "Unknown"
        confidence = 0.0

        if True in matches:
            idx = matches.index(True)
            name = known_face_names[idx]
            dist = face_recognition.face_distance(known_face_encodings, face_encoding)
            confidence = 1 - dist[idx]

        # Handle Unknown vs Known
        if name not in active_users:
            img_payload = None
            if name == "Unknown":
                # Crop face from original frame (scale back by 4)
                face_crop = frame[top*4:bottom*4, left*4:right*4]
                img_payload = convert_frame_to_base64(face_crop)
            
            notify_cloud(name, confidence, img_payload)
        
        active_users[name] = time.time()

    # Exit Tracker
    now = time.time()
    for user in list(active_users.keys()):
        if now - active_users[user] > 10:
            if user != "Unknown": # Don't send exits for unknowns
                try: requests.post(EXIT_URL, json={"name": user}, timeout=5)
                except: pass
            del active_users[user]

    cv2.imshow("SentriCore Surveillance", frame)
    if cv2.waitKey(1) & 0xFF == 27: break

video.release()
cv2.destroyAllWindows()