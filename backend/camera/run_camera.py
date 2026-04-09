import cv2
import face_recognition
import numpy as np
import requests
import base64
import time
import os
from datetime import datetime

# --- CONFIGURATION ---
# Replace with your actual Render URL
RENDER_URL = "https://your-app-name.onrender.com/detect_face"

# Since we don't have direct DB access, we'll track active users locally 
# just to handle the "EXIT" logic before telling the cloud.
active_users = {} 
process_this_frame = True

def frame_to_base64(frame):
    """Converts a CV2 frame to a base64 string for the API."""
    _, buffer = cv2.imencode('.jpg', frame)
    img_str = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/jpeg;base64,{img_str}"

def send_to_cloud(frame, name="Unknown"):
    """Sends the detection event to the Render Backend."""
    payload = {
        "image": frame_to_base64(frame)
    }
    try:
        response = requests.post(RENDER_URL, json=payload, timeout=5)
        if response.status_code == 200:
            result = response.json()
            return result.get("detected", "Unknown")
    except Exception as e:
        print(f"📡 Cloud Connection Error: {e}")
    return "Error"

# Start Video
video = cv2.VideoCapture(0)

print("--- SentriCore Edge Node Active ---")
print(f"Targeting: {RENDER_URL}")

while True:
    ret, frame = video.read()
    if not ret: break

    # 1. Resize for i3 Performance
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    if process_this_frame:
        # 2. Local Face Detection (Find where faces are)
        locations = face_recognition.face_locations(rgb_small_frame)
        
        if locations:
            # 3. Send the image to the Cloud Brain
            # The Cloud handles the heavy encoding comparison and DB logging
            detected_name = send_to_cloud(frame)
            
            if detected_name and detected_name != "Unknown" and detected_name != "Error":
                active_users[detected_name] = time.time()
                print(f"✅ Recognized: {detected_name}")
            elif detected_name == "Unknown":
                print("⚠️ Alert: Unknown person detected!")

    process_this_frame = not process_this_frame

    # 4. Local Exit Tracker 
    # --- Inside your laptop while loop ---
    now = time.time()
    for user in list(active_users.keys()):
        if now - active_users[user] > 10:  # User hasn't been seen for 10 seconds
            print(f"🚪 Sending EXIT for {user} to Cloud...")
            
            # --- CALL THE NEW CLOUD ROUTE ---
            try:
                # Replace with your actual Render URL
                EXIT_URL = "https://your-app-name.onrender.com/exit_user"
                requests.post(EXIT_URL, json={"name": user}, timeout=5)
            except Exception as e:
                print(f"Failed to send EXIT log: {e}")
                
            del active_users[user]

    # Display for local monitoring
    cv2.putText(frame, "SentriCore Live: Connected to Cloud", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 210, 255), 2)
    cv2.imshow("SentriCore Surveillance (Edge)", frame)

    if cv2.waitKey(1) & 0xFF == 27: break

video.release()
cv2.destroyAllWindows()