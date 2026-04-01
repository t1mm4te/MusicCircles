import tempfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment() -> Any:
    """Настройка изолированного окружения для e2e-набора."""
    with tempfile.TemporaryDirectory() as temp_dir:
        import os

        os.environ["DOWNLOAD_FOLDER"] = temp_dir
        os.environ["TB_TOKEN"] = "test_token"
        os.environ["AUDIO_RECEIVER_API_URL"] = "http://test-audio-api"
        os.environ["MEDIA_PROCESSOR_API_URL"] = "http://test-media-api"
        os.environ["DATABASE_API_URL"] = "http://test-database-api"
        yield


@pytest.fixture
def context_factory():
    def _factory() -> MagicMock:
        context = MagicMock()
        context.user_data = {}
        context.bot = AsyncMock()
        return context

    return _factory


@pytest.fixture
def message_update_factory():
    def _factory(
        *,
        text: str,
        user_id: int = 123,
        username: str = "test_user",
        chat_id: int = 456,
    ) -> MagicMock:
        update = MagicMock()
        update.callback_query = None

        update.message = MagicMock()
        update.message.text = text
        update.message.reply_text = AsyncMock()

        update.message.from_user = MagicMock()
        update.message.from_user.id = user_id
        update.message.from_user.username = username

        update.effective_chat = MagicMock()
        update.effective_chat.id = chat_id
        return update

    return _factory


@pytest.fixture
def callback_update_factory():
    def _factory(
        *,
        data: str,
        user_id: int = 123,
        username: str = "test_user",
        chat_id: int = 456,
    ) -> MagicMock:
        update = MagicMock()
        update.message = None

        update.callback_query = MagicMock()
        update.callback_query.data = data
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()

        update.callback_query.from_user = MagicMock()
        update.callback_query.from_user.id = user_id
        update.callback_query.from_user.username = username

        update.effective_chat = MagicMock()
        update.effective_chat.id = chat_id
        return update

    return _factory
