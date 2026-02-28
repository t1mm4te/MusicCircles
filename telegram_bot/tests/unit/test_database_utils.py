"""Тесты для telegram_bot/src/database_utils.py — логирование в БД."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from src.database_utils import log_interaction


class TestLogInteraction:
    """Тесты log_interaction."""

    @patch("src.database_utils.httpx.AsyncClient")
    async def test_success(self, mock_client_cls):
        """Успешное логирование возвращает True."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await log_interaction(
            user_id=123,
            username="testuser",
            interaction_type="Поиск песни"
        )
        assert result is True

    @patch("src.database_utils.httpx.AsyncClient")
    async def test_http_error_returns_false(self, mock_client_cls):
        """HTTP ошибка возвращает False."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(), response=mock_response
            )
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await log_interaction(
            user_id=123,
            username="testuser",
            interaction_type="Поиск песни"
        )
        assert result is False

    @patch("src.database_utils.httpx.AsyncClient")
    async def test_connection_error_returns_false(self, mock_client_cls):
        """Ошибка соединения возвращает False."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.RequestError("Connection refused", request=MagicMock())
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await log_interaction(
            user_id=123,
            username="testuser",
            interaction_type="Поиск песни"
        )
        assert result is False

    @patch("src.database_utils.httpx.AsyncClient")
    async def test_unexpected_error_returns_false(self, mock_client_cls):
        """Непредвиденная ошибка возвращает False."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Unexpected"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await log_interaction(
            user_id=123,
            username=None,
            interaction_type="Создание видео"
        )
        assert result is False
