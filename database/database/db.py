import sqlite3
import os
from contextlib import contextmanager
from typing import Generator

DATABASE_PATH = "/app/data/database.db"


def init_database():
    """Инициализация базы данных и создание таблиц."""
    # Создаем директорию для базы данных, если она не существует
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()

        # Создание таблицы пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        """)

        # Создание таблицы видов взаимодействия
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interaction_types (
                type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                interaction_type CHAR(30) UNIQUE NOT NULL
            )
        """)

        # Создание таблицы взаимодействий
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

        # Добавляем только два типа взаимодействий
        default_interactions = [
            "Поиск песни",
            "Создание видео"
        ]

        for interaction in default_interactions:
            cursor.execute("""
                INSERT OR IGNORE INTO interaction_types (interaction_type) 
                VALUES (?)
            """, (interaction,))

        conn.commit()


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Контекстный менеджер для работы с базой данных."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Для возврата результатов как словарей
    try:
        yield conn
    finally:
        conn.close()
