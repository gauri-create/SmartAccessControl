import sqlite3
import os

# Ensuring the directory exists before creating the DB file
DB_DIR = "backend/database"
DB_PATH = os.path.join(DB_DIR, "attendance.db")

if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Enable Foreign Key support in SQLite
    cur.execute("PRAGMA foreign_keys = ON;")

    # ==========================================================
    # 1. USERS TABLE (Core Identity & Auth)
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL, -- 'owner', 'hr', 'staff'
        status TEXT DEFAULT 'active', -- 'active' or 'inactive'
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ==========================================================
    # 2. FACE DATA TABLE (Biometric Storage)
    # ==========================================================
    # Linked to users. If a user is deleted, their face data vanishes.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS face_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        encoding BLOB NOT NULL, -- 128-dimensional vector as binary
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ==========================================================
    # 3. LOGS TABLE (Surveillance Activity)
    # ==========================================================
    # Prepared for multi-camera scaling and AI confidence tracking
    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,           -- Name or 'Unknown'
        status TEXT,         -- 'ENTRY', 'EXIT', or 'ALERT'
        camera_id INTEGER DEFAULT 1, 
        confidence REAL,     -- How sure the AI was (0.0 to 1.0)
        image_path TEXT,     -- Only populated for 'Unknown' or 'Alerts'
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ==========================================================
    # 4. INITIAL SETUP (Default Admin)
    # ==========================================================
    cur.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if not cur.fetchone():
        cur.execute("""
        INSERT INTO users (username, name, password, role, status)
        VALUES (?, ?, ?, ?, ?)
        """, ("admin", "System Admin", "admin@123", "owner", "active"))
        print("[DB] Initialized: System Admin account created.")

    conn.commit()
    conn.close()
    print(f"[DB] Success: Database initialized at {DB_PATH}")

if __name__ == "__main__":
    # OPTIONAL: To completely wipe and restart, uncomment the lines below:
    # if os.path.exists(DB_PATH):
    #     os.remove(DB_PATH)
    #     print("[DB] Existing database deleted for a fresh start.")
    
    init_db()