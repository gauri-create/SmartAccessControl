import sqlite3

DB_PATH = "backend/database/attendance.db"

def log_to_db(name, status, image_path="", confidence=0.0):
    """Logs activity to the database with camera and confidence info."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # camera_id defaults to 1 for your current setup
        cursor.execute("""
            INSERT INTO logs (name, status, image_path, confidence, camera_id)
            VALUES (?, ?, ?, ?, ?)
        """, (name, status, image_path, float(confidence), 1))
        
        conn.commit()
        conn.close()
        print(f"[LOG] {status}: {name} ({round(confidence*100, 2)}%)")
    except Exception as e:
        print(f"[ERROR] Logging failed: {e}")