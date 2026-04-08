# import sqlite3
# import os

# def reset_database():
#     # This finds the folder where del.py is located
#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     # This joins that folder with the database name
#     db_path = os.path.join(script_dir, "attendance.db")

#     print(f"Targeting Database at: {db_path}")
    
#     if not os.path.exists(db_path):
#         print(f"❌ Error: The file {db_path} does not exist!")
#         return

#     conn = sqlite3.connect(db_path) 
#     cursor = conn.cursor()

#     try:
#         # 1. Delete everyone except Admin (ID 1)
#         cursor.execute("DELETE FROM users WHERE id != 1")
        
#         # 2. Reset the auto-increment counter
#         cursor.execute("UPDATE sqlite_sequence SET seq = 1 WHERE name = 'users'")
        
#         # 3. Clear logs
#         cursor.execute("DELETE FROM logs")
        
#         conn.commit()
        
#         # Verify result
#         cursor.execute("SELECT username FROM users")
#         user = cursor.fetchone()
#         if user:
#             print(f"✅ Success! Only '{user[0]}' remains in the database.")
#         else:
#             print("⚠️ Database is now empty (Admin was missing or deleted).")
        
#     except Exception as e:
#         print(f"❌ Error: {e}")
#     finally:
#         conn.close()

# if __name__ == "__main__":
#     reset_database()




# import sqlite3
# import os

# def reset_database():
#     # Automatically find the database sitting next to this script
#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     db_path = os.path.join(script_dir, "attendance.db")

#     print(f"Targeting Database at: {db_path}")
    
#     if not os.path.exists(db_path):
#         print(f"❌ Error: The file {db_path} does not exist!")
#         return

#     conn = sqlite3.connect(db_path) 
#     cursor = conn.cursor()

#     try:
#         # 1. Delete everyone except Admin (ID 1) from users table
#         cursor.execute("DELETE FROM users WHERE id != 1")
        
#         # 2. Delete all facial encodings except for Admin (user_id 1)
#         # Based on your screenshot, these are the rows with user_id 2, 3, 4, 5, 6
#         cursor.execute("DELETE FROM face_data WHERE user_id != 1")
        
#         # 3. Reset auto-increment counters for both tables
#         cursor.execute("UPDATE sqlite_sequence SET seq = 1 WHERE name = 'users'")
#         cursor.execute("UPDATE sqlite_sequence SET seq = 1 WHERE name = 'face_data'")
        
#         # 4. Clear activity logs
#         cursor.execute("DELETE FROM logs")
        
#         conn.commit()
        
#         # Verification
#         cursor.execute("SELECT COUNT(*) FROM face_data")
#         faces_left = cursor.fetchone()[0]
#         print(f"✅ Success! Database cleaned. {faces_left} face encoding(s) remaining.")
        
#     except Exception as e:
#         print(f"❌ Error: {e}")
#     finally:
#         conn.close()

# if __name__ == "__main__":
#     reset_database()