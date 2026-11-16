import os
import sqlite3

# --- SQLITE BAZA SOZLAMALARI ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_database.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS channels (
    chat_id INTEGER PRIMARY KEY,
    title TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT,
    message_id INTEGER,
    channel_id INTEGER
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    phone TEXT,
    status INTEGER DEFAULT 0
)
""")
conn.commit()

watched_chats_cache = set()


def refresh_cache():
    cursor.execute("SELECT chat_id FROM channels")
    watched_chats_cache.clear()
    for row in cursor.fetchall():
        watched_chats_cache.add(row[0])


refresh_cache()


def add_channel_db(chat_id, title):
    cursor.execute("INSERT OR REPLACE INTO channels (chat_id, title) VALUES (?, ?)", (chat_id, title))
    conn.commit()
    refresh_cache()


def remove_channel_db(chat_id):
    cursor.execute("DELETE FROM channels WHERE chat_id = ?", (chat_id,))
    deleted = cursor.rowcount
    conn.commit()
    refresh_cache()
    return deleted


def get_channels_db():
    cursor.execute("SELECT chat_id, title FROM channels")
    return cursor.fetchall()


def save_file_db(file_name, message_id, db_channel):
    cursor.execute(
        "INSERT INTO files (file_name, message_id, channel_id) VALUES (?, ?, ?)",
        (file_name, message_id, db_channel)
    )
    conn.commit()


def search_files_db(query, limit=10):
    cursor.execute(
        "SELECT file_name, message_id, channel_id FROM files WHERE file_name LIKE ? ORDER BY id DESC LIMIT ?",
        (f"%{query}%", limit)
    )
    return cursor.fetchall()


def set_user_logged_in(user_id, phone, status=1):
    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, phone, status) VALUES (?, ?, ?)",
        (user_id, phone, status)
    )
    conn.commit()


def is_user_logged_in(user_id):
    cursor.execute("SELECT status FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return bool(row and row[0] == 1)
