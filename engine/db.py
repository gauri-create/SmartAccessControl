import csv
import sqlite3
con = sqlite3.connect("AIassistant.db")
cursor = con.cursor()

# query = """
# CREATE TABLE IF NOT EXISTS sys_command (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     name TEXT NOT NULL UNIQUE,
#     path TEXT NOT NULL
# )
# """
# cursor.execute(query)

# query = """
# CREATE TABLE IF NOT EXISTS web_command (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     name TEXT NOT NULL UNIQUE,
#     url TEXT NOT NULL
# )
# """
# cursor.execute(query)
# # Delete all records
# cursor.execute("DELETE FROM sys_command;")
# cursor.execute("DELETE FROM web_command;")

# cursor.execute("DELETE FROM sys_command WHERE name=?",
#                ("chrome",))
# query = """
#      INSERT INTO sys_command VALUES(
#      null, 
#      'excel',
#      'C:\\Program Files\\Microsoft Office\\root\\Office16\\EXCEL.EXE'
#      )
# """
# cursor.execute(query)

# web_commands = (
#     ("linkedin", "https://www.linkedin.com//in//gauribelokar"),
    
# )

# cursor.executemany(
#     "INSERT OR IGNORE INTO web_command (name, url) VALUES (?, ?)",
#     web_commands
#     )

# cursor.execute("DELETE FROM web_command WHERE name= ?",
#                ("spotify",))

# query = """
#     INSERT INTO web_command VALUES(
#     null, 
#    'spotify',
#    'https://open.spotify.com'
#     )
# """
# # cursor.execute(query)

# cursor.execute("DROP TABLE IF EXISTS contacts")


# # Create table if it doesn't exist
# cursor.execute('''
# CREATE TABLE IF NOT EXISTS contacts (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     first_name VARCHAR(100),
#     middle_name VARCHAR(100),
#     surname VARCHAR(100),
#     mobile_no VARCHAR(255),
#     email VARCHAR(255)
# )
# ''')

# # Map your database columns to CSV headers
# column_mapping = {
#     "first_name": "First Name",
#     "middle_name": "Middle Name",
#     "surname": "Last Name",
#     "mobile_no": "Phone 1 - Value",
#     "email": "E-mail 1 - Value"
# }

# with open('contacts.csv', 'r', encoding='utf-8') as csvfile:
#     reader = csv.DictReader(csvfile)  # use DictReader to read by header

#     for row in reader:
#         # Build data list in correct order
#         data_to_insert = [
#             row.get(column_mapping["first_name"], "").strip() or None,
#             row.get(column_mapping["middle_name"], "").strip() or None,
#             row.get(column_mapping["surname"], "").strip() or None,
#             row.get(column_mapping["mobile_no"], "").strip() or None,
#             row.get(column_mapping["email"], "").strip() or None
#         ]

#         # Skip completely empty rows (optional)
#         if all(v is None for v in data_to_insert):
#             continue

#         cursor.execute(
#             "INSERT INTO contacts (first_name, middle_name, surname, mobile_no, email) VALUES (?, ?, ?, ?, ?)",
#             data_to_insert
#         )

# query = 'gauri'
# query = query.strip().lower()

# # Execute SQL
# cursor.execute("""
#     SELECT mobile_no 
#     FROM contacts
#     WHERE LOWER(first_name) = ? 
#        OR LOWER(middle_name) = ? 
#        OR LOWER(surname) = ?
# """, (query, query, query))

# results = cursor.fetchall()

# # Check if any results found
# if results:
#     for mobile in results:
#         print(mobile[0])
# else:
#     print("No contact found.")

# # con.commit()
# con.close()

# cursor.execute(''' DROP TABLE contact''')
#  Create a table with the desired columns
# cursor.execute('''CREATE TABLE IF NOT EXISTS contact (id integer primary key, name VARCHAR(200), mobile_no VARCHAR(255), email VARCHAR(255) NULL)''')
# con.commit()
# con.close()


# Specify the column indices you want to import (0-based index)
# Example: Importing the 1st and 3rd columns

# desired_columns_indices = [0, 20]

# # Read data from CSV and insert into SQLite table for the desired columns
# with open('contacts.csv', 'r', encoding='utf-8') as csvfile:
#     csvreader = csv.reader(csvfile)
#     for row in csvreader:
#         selected_data = [row[i] for i in desired_columns_indices]
#         cursor.execute(''' INSERT INTO contact (id, 'name', 'mobile_no') VALUES (null, ?, ?);''', tuple(selected_data))

# # Commit changes and close connection
# con.commit()
# con.close()