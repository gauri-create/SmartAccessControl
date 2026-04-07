import sqlite3
from datetime import datetime

DB_PATH = "backend/database/attendance.db"


def log_to_db(name, status, image):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO logs (name, status, timestamp, image)
        VALUES (?, ?, ?, ?)
    """, (
        name,
        status,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        image
    ))

    conn.commit()
    conn.close()