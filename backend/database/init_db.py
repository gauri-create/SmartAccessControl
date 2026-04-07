import sqlite3
import os

DB = "backend/database/attendance.db"

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # =========================
    # USERS TABLE (AUTH SYSTEM)
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        status TEXT DEFAULT 'active'
    )
    """)

    # =========================
    # FACE DATA TABLE
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS face_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        encoding BLOB NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # =========================
    # LOGS TABLE (ATTENDANCE)
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        status TEXT,
        timestamp TEXT,
        image TEXT
    )
    """)

    # =========================
    # DEFAULT OWNER (ONLY ONCE)
    # =========================
    cur.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    owner = cur.fetchone()

    if not owner:
        cur.execute("""
        INSERT INTO users (username, name, password, role, status)
        VALUES (?, ?, ?, ?, ?)
        """, ("admin", "System Admin", "admin@123", "owner", "active"))

        print("[DB] Owner account created")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()