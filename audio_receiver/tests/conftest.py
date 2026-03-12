import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Нужно замокать dotenv и переменные окружения ДО импорта audio_receiver_utils,
# т.к. он делает load_dotenv() + os.getenv() на уровне модуля.
os.environ.setdefault("YANDEX_MUSIC_API_TOKEN", "fake_test_token")

# Мокаем yandex_music, чтобы не требовать реальную установку
_mock_ym = MagicMock()
sys.modules["yandex_music"] = _mock_ym
