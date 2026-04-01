from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """Path to a temporary SQLite database for isolated tests."""
    return str(tmp_path / "test_database.db")


@pytest.fixture
def patched_db(db_path):
    """Initialize a temporary DB and patch database path for service tests."""
    with patch("database.db.DATABASE_PATH", db_path):
        from database.db import get_db_connection, init_database

        init_database()
        with get_db_connection() as conn:
            yield conn