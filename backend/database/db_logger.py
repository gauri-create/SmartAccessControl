import os
import psycopg2
import sqlite3

IS_RENDER = os.getenv('RENDER')

def log_to_db(name, status, image_path="", confidence=0.0):
    """
    STRICTLY ALIGNED VERSION: Matches your SQLite screenshot exactly.
    Columns: name, status, camera_id, confidence, image_path
    """
    conn = None
    try:
        if IS_RENDER:
            # --- CLOUD: PostgreSQL ---
            database_url = os.getenv('DATABASE_URL')
            if database_url and database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            
            conn = psycopg2.connect(database_url)
            cursor = conn.cursor()
            placeholder = "%s"
        else:
            # --- LOCAL: SQLite ---
            local_db = "backend/database/attendance.db"
            conn = sqlite3.connect(local_db)
            cursor = conn.cursor()
            placeholder = "?"

        # Query using the exact column names from your screenshot
        query = f"""
            INSERT INTO logs (name, status, camera_id, confidence, image_path)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
        """
        
        # camera_id = 1 by default
        cursor.execute(query, (name, status, 1, float(confidence), image_path))
        
        conn.commit()
        print(f"✅ [LOG] {status}: {name} ({round(confidence*100, 2)}%)")

    except Exception as e:
        print(f"❌ [DB ERROR] {e}")
    finally:
        if conn:
            conn.close()