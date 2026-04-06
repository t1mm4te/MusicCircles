import os
from pathlib import Path
from unittest.mock import patch
import pytest

@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    """
    Срабатывает ДО импорта модулей приложения.
    Устанавливаем переменную окружения, чтобы init_database() в __init__.py 
    сразу знала, что работать нужно в памяти.
    """
    os.environ["DATABASE_PATH"] = ":memory:"

@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """Путь к временному файлу БД для тестов, которым нужен диск."""
    return str(tmp_path / "test_database.db")

@pytest.fixture
def patched_db(db_path):
    """Фикстура для изоляции конкретных тестов."""
    with patch("database.db.DATABASE_PATH", db_path):
        from database.db import get_db_connection, init_database
        init_database()
        with get_db_connection() as conn:
            yield conn