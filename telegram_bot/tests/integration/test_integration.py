import os
import pytest
import httpx
import tempfile
from unittest.mock import patch, AsyncMock, MagicMock

from src.api_utils import (
    search_for_tracks,
    download_track_stream,
    trim_audio,
    create_video,
    TrackInfo
)
from src.database_utils import log_interaction


@pytest.mark.asyncio
async def test_search_song_integration():
    """Сценарий 1: Успешный GET /search к audio_receiver."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"id": "1", "title": "Test Song", "artists": [
                "Test Artist"], "duration": 180000, "url": "http://test"}
        ]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await search_for_tracks("Test query")

        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], TrackInfo)
        assert result[0].title == "Test Song"


@pytest.mark.asyncio
async def test_search_song_empty_or_error():
    """Сценарий 2: Ошибка при GET /search к audio_receiver."""
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=MagicMock(), response=MagicMock())

        result = await search_for_tracks("Test query")

        # Функция должна перехватить ошибку и вернуть None или пустой список
        assert result is None or result == []


@pytest.mark.asyncio
async def test_download_stream_chunks():
    """Сценарий 3: Тестирование склеивания бинарных чанков (download_track_stream)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        expected_output_path = os.path.join(temp_dir, "test_track.mp3")

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        # Мокируем асинхронный итератор aiter_bytes

        async def mock_aiter_bytes():
            yield b"chunk1"
            yield b"chunk2"
        mock_response.aiter_bytes = mock_aiter_bytes

        mock_context_manager = MagicMock()
        mock_context_manager.__aenter__.return_value = mock_response
        mock_context_manager.__aexit__ = AsyncMock()

        with patch("httpx.AsyncClient.stream", return_value=mock_context_manager):
            result_path = await download_track_stream("test_track", temp_dir)

            assert result_path == expected_output_path
            assert os.path.exists(result_path)
            with open(result_path, "rb") as f:
                content = f.read()
            assert content == b"chunk1chunk2"


@pytest.mark.asyncio
async def test_trim_audio_valid_limits():
    """Сценарий 4: Успешный POST /trim_audio в media_processor."""
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(temp_dir, "input.mp3")
        output_path = os.path.join(temp_dir, "output.mp3")
        with open(input_path, "wb") as f:
            f.write(b"dummy")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"trimmed_audio"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await trim_audio(input_path, 0, 30, output_path)

            assert result is True
            assert os.path.exists(output_path)
            with open(output_path, "rb") as f:
                assert f.read() == b"trimmed_audio"


@pytest.mark.asyncio
async def test_trim_audio_boundary_exceeded():
    """Сценарий 5: Невалидные параметры обрезки (>55 сек)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(temp_dir, "input.mp3")
        output_path = os.path.join(temp_dir, "output.mp3")
        with open(input_path, "wb") as f:
            f.write(b"dummy")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "400 Bad Request", request=MagicMock(), response=MagicMock())

            result = await trim_audio(input_path, 0, 60, output_path)

            assert result is False
            assert not os.path.exists(output_path)


@pytest.mark.asyncio
async def test_create_video_render_success():
    """Сценарий 6: Успешный POST /create_video в media_processor."""
    with tempfile.TemporaryDirectory() as temp_dir:
        audio_path = os.path.join(temp_dir, "audio.mp3")
        image_path = os.path.join(temp_dir, "image.jpg")
        output_path = os.path.join(temp_dir, "output.mp4")

        with open(audio_path, "wb") as f:
            f.write(b"audio")
        with open(image_path, "wb") as f:
            f.write(b"image")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"video_data"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await create_video(audio_path, image_path, output_path)

            assert result is True
            assert os.path.exists(output_path)
            with open(output_path, "rb") as f:
                assert f.read() == b"video_data"


@pytest.mark.asyncio
async def test_create_video_invalid_media():
    """Сценарий 7: Ошибка POST /create_video из-за невалидных медиа-файлов."""
    with tempfile.TemporaryDirectory() as temp_dir:
        audio_path = os.path.join(temp_dir, "audio.txt")
        image_path = os.path.join(temp_dir, "image.txt")
        output_path = os.path.join(temp_dir, "output.mp4")

        with open(audio_path, "wb") as f:
            f.write(b"bad")
        with open(image_path, "wb") as f:
            f.write(b"bad")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "400 Bad Request", request=MagicMock(), response=MagicMock())

            result = await create_video(audio_path, image_path, output_path)

            assert result is False


@pytest.mark.asyncio
async def test_render_timeout_handling():
    """Сценарий 8: Таймаут рендера видео."""
    with tempfile.TemporaryDirectory() as temp_dir:
        audio_path = os.path.join(temp_dir, "audio.mp3")
        image_path = os.path.join(temp_dir, "image.jpg")
        output_path = os.path.join(temp_dir, "output.mp4")

        with open(audio_path, "wb") as f:
            f.write(b"audio")
        with open(image_path, "wb") as f:
            f.write(b"image")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Timeout")

            result = await create_video(audio_path, image_path, output_path)

            assert result is False


@pytest.mark.asyncio
async def test_database_log_interaction():
    """Сценарий 9: Успешный POST /log-interaction/ в базу данных."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await log_interaction(user_id=123, username="test_user", interaction_type="search")

        assert result is True
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_database_network_failure():
    """Сценарий 10: Сеть недоступна при обращении к БД (fail-safe)."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.RequestError("Connection refused")

        result = await log_interaction(user_id=123, username="test_user", interaction_type="search")

        # Функционал бота не должен падать, возвращаем False и идем дальше
        assert result is False
