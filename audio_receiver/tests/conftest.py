import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure top-level project modules are importable in container test runs.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Нужно замокать dotenv и переменные окружения ДО импорта audio_receiver_utils,
# т.к. он делает load_dotenv() + os.getenv() на уровне модуля.
os.environ.setdefault("YANDEX_MUSIC_API_TOKEN", "fake_test_token")

# Мокаем yandex_music, чтобы не требовать реальную установку
_mock_ym = MagicMock()
sys.modules["yandex_music"] = _mock_ym
