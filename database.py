import sqlite3

# connect to database (creates file automatically if not exists)
conn = sqlite3.connect("complaints.db")

# create cursor
cursor = conn.cursor()

# create users table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL
)
""")

print("Users table created successfully!")

# save and close
conn.commit()
conn.close()