from datetime import datetime
from backend.database.db import get_connection

def log_to_db(name, status, image):
    conn = get_connection()
    cursor = conn.cursor()

    timestamp= datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(""" 
        INSERT  INTO logs(name,status, timestamp, image)
        VALUES(?,?,?,?)
    """, (name, status, timestamp, image))

    conn.commit()
    conn.close