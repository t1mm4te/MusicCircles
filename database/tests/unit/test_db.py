import pytest
import sqlite3
from unittest.mock import patch


class TestInitDatabase:

    def test_creates_tables(self, db_path):
        with patch("database.db.DATABASE_PATH", db_path):
            from database.db import init_database
            init_database()

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = {row[0] for row in cursor.fetchall()}
            conn.close()

        assert "users" in tables
        assert "interaction_types" in tables
        assert "interactions" in tables

    def test_creates_default_interaction_types(self, db_path):
        with patch("database.db.DATABASE_PATH", db_path):
            from database.db import init_database
            init_database()

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT interaction_type FROM interaction_types ORDER BY type_id")
            types = [row[0] for row in cursor.fetchall()]
            conn.close()

        assert "Поиск песни" in types
        assert "Создание видео" in types

    def test_idempotent_init(self, db_path):
        with patch("database.db.DATABASE_PATH", db_path):
            from database.db import init_database
            init_database()

            conn = sqlite3.connect(db_path)
            conn.execute("INSERT INTO users (user_id, username) VALUES (1, 'alice')")
            conn.commit()
            conn.close()

            init_database()

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users WHERE user_id = 1")
            row = cursor.fetchone()
            conn.close()

        assert row is not None
        assert row[0] == "alice"


class TestGetDbConnection:
    def test_returns_connection(self, db_path):
        with patch("database.db.DATABASE_PATH", db_path):
            from database.db import init_database, get_db_connection
            init_database()

            with get_db_connection() as conn:
                assert conn is not None
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                assert result[0] == 1

    def test_connection_has_row_factory(self, db_path):
        with patch("database.db.DATABASE_PATH", db_path):
            from database.db import init_database, get_db_connection
            init_database()

            with get_db_connection() as conn:
                assert conn.row_factory == sqlite3.Row
