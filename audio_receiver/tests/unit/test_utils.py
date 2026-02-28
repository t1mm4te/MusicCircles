"""Тесты для audio_receiver/audio_receiver_utils.py — утилиты Yandex Music."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import audio_receiver_utils as utils


class TestInitClient:
    """Тесты init_client."""

    async def test_init_client_success(self):
        """Успешная инициализация клиента."""
        mock_client_instance = AsyncMock()
        mock_client_instance.init = AsyncMock(return_value=mock_client_instance)

        with patch("audio_receiver_utils.ClientAsync", return_value=mock_client_instance):
            await utils.init_client()
            assert utils.client is not None

    async def test_init_client_token_error(self):
        """Ошибка при инициализации с невалидным токеном."""
        mock_client_instance = AsyncMock()
        mock_client_instance.init = AsyncMock(side_effect=Exception("Invalid token"))

        with patch("audio_receiver_utils.ClientAsync", return_value=mock_client_instance):
            with pytest.raises(Exception, match="Invalid token"):
                await utils.init_client()


class TestFindTracksByName:
    """Тесты find_tracks_by_name."""

    async def test_tracks_found(self):
        """Найдены треки по запросу."""
        mock_track1 = MagicMock()
        mock_track1.id = 1
        mock_track1.title = "Song A"

        mock_tracks_result = MagicMock()
        mock_tracks_result.results = [mock_track1]

        mock_search_result = MagicMock()
        mock_search_result.tracks = mock_tracks_result

        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=mock_search_result)
        utils.client = mock_client

        result = await utils.find_tracks_by_name("test query")
        assert result is not None
        assert len(result) == 1
        assert result[0].id == 1
        mock_client.search.assert_called_once_with("test query", type_="track")

    async def test_no_tracks_found(self):
        """Пустой результат поиска (tracks is None)."""
        mock_search_result = MagicMock()
        mock_search_result.tracks = None

        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=mock_search_result)
        utils.client = mock_client

        result = await utils.find_tracks_by_name("nonexistent")
        assert result is None

    async def test_tracks_empty_results(self):
        """Треки найдены, но список пустой."""
        mock_tracks_result = MagicMock()
        mock_tracks_result.results = []

        mock_search_result = MagicMock()
        mock_search_result.tracks = mock_tracks_result

        mock_client = AsyncMock()
        mock_client.search = AsyncMock(return_value=mock_search_result)
        utils.client = mock_client

        result = await utils.find_tracks_by_name("empty")
        assert result == []

    async def test_search_api_error(self):
        """Ошибка API при поиске."""
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(side_effect=Exception("API Error"))
        utils.client = mock_client

        with pytest.raises(Exception, match="API Error"):
            await utils.find_tracks_by_name("error_query")


class TestGetTrackInfo:
    """Тесты get_track_info."""

    async def test_success(self):
        """Успешное получение информации о треке."""
        mock_track = MagicMock()
        mock_track.title = "Test Song"
        mock_track.duration_ms = 180000

        mock_client = AsyncMock()
        mock_client.tracks = AsyncMock(return_value=[mock_track])
        utils.client = mock_client

        result = await utils.get_track_info(12345)
        assert result == mock_track
        mock_client.tracks.assert_called_once_with(12345)

    async def test_track_not_found(self):
        """Трек не найден (пустой список)."""
        mock_client = AsyncMock()
        mock_client.tracks = AsyncMock(return_value=[])
        utils.client = mock_client

        with pytest.raises(IndexError):
            await utils.get_track_info(99999)


class TestGetTrackCover:
    """Тесты get_track_cover."""

    async def test_success(self):
        """Успешное получение обложки."""
        mock_track = MagicMock()
        mock_cover_bytes = b"\x89PNG\r\n\x1a\n..."
        mock_track.download_cover_bytes_async = AsyncMock(return_value=mock_cover_bytes)

        result = await utils.get_track_cover(mock_track)
        assert result == mock_cover_bytes
        mock_track.download_cover_bytes_async.assert_called_once_with(size="200x200")


class TestGetTrackBytes:
    """Тесты get_track_bytes."""

    async def test_success(self):
        """Успешное получение байтов трека."""
        mock_track = MagicMock()
        mock_download_info = MagicMock()
        mock_download_info.codec = "mp3"
        mock_download_info.bitrate_in_kbps = 192

        mock_track.get_download_info_async = AsyncMock(return_value=[mock_download_info])
        mock_track.download_bytes_async = AsyncMock(return_value=b"audio_bytes")

        result = await utils.get_track_bytes(mock_track)
        assert result == b"audio_bytes"
        mock_track.download_bytes_async.assert_called_once_with("mp3", 192)

    async def test_no_download_info(self):
        """download_info_list is None → возвращает None."""
        mock_track = MagicMock()
        mock_track.get_download_info_async = AsyncMock(return_value=None)

        result = await utils.get_track_bytes(mock_track)
        assert result is None