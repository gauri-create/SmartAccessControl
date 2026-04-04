import sqlite3
import os

DB_PATH = "backend/database/attendance.db"

def init_db(reset=False):
    # ⚠️ Optional reset (only when you WANT to wipe data)
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("Old database deleted.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ---------------- USERS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        image TEXT,
        encoding BLOB
    )
    """)

    # ---------------- LOGS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        status TEXT,
        timestamp TEXT,
        image TEXT
    )
    """)

    conn.commit()
    conn.close()

    print("Database initialized successfully.")


if __name__ == "__main__":
    # ⚠️ Change to True ONLY if you want to wipe everything
    init_db(reset=False)