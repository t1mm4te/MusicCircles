import sqlite3
import os
from contextlib import contextmanager
from typing import Generator

# Приоритет переменной окружения для тестов
DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/data/database.db")

def init_database():
    """Инициализация базы данных и создание таблиц."""
    # Если мы не в режиме "в памяти", создаем папку
    if DATABASE_PATH != ":memory:":
        db_dir = os.path.dirname(DATABASE_PATH)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        # Создание таблиц
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interaction_types (
                type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                interaction_type CHAR(30) UNIQUE NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                interaction_type_id INTEGER NOT NULL,
                interaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (interaction_type_id) REFERENCES interaction_types (type_id)
            )
        """)
        # Наполнение справочника
        for interaction in ["Поиск песни", "Создание видео"]:
            cursor.execute("INSERT OR IGNORE INTO interaction_types (interaction_type) VALUES (?)", (interaction,))
        conn.commit()

@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Контекстный менеджер для работы с базой данных."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()