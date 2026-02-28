import pytest
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import httpx

from src.api_utils import (
    TrackInfo,
    search_for_tracks,
    get_track_info,
    download_track_stream,
    download_cover,
    trim_audio,
    create_video,
)


class TestSearchForTracks:

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_success_with_results(self, mock_client_cls):
        """Успешный поиск."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"id": 1, "title": "Song A", "artists": ["Artist1"], "duration": 180000},
                {"id": 2, "title": "Song B", "artists": ["Artist2", "Artist3"], "duration": 240000},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await search_for_tracks("test")
        assert result is not None
        assert len(result) == 2
        assert isinstance(result[0], TrackInfo)
        assert result[0].id == 1
        assert result[0].title == "Song A"
        assert result[0].duration == 180  # 180000 // 1000
        assert result[1].artists == "Artist2, Artist3"

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_empty_results(self, mock_client_cls):
        """Поиск без результатов."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await search_for_tracks("nothing")
        assert result is not None
        assert result == []

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_http_error(self, mock_client_cls):
        """HTTP ошибка (4xx/5xx) возвращает None."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(), response=mock_response
            )
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await search_for_tracks("test")
        assert result is None

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_connection_error(self, mock_client_cls):
        """Ошибка соединения возвращает None."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.RequestError("Connection refused", request=MagicMock())
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await search_for_tracks("test")
        assert result is None


class TestGetTrackInfo:
    """Тесты get_track_info."""

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_success(self, mock_client_cls):
        """Успешное получение длительности трека."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"duration": 180000}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await get_track_info("12345")
        assert result == 180  # 180000 // 1000

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_http_error_returns_none(self, mock_client_cls):
        """HTTP ошибка возвращает None."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "404", request=MagicMock(), response=mock_response
            )
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await get_track_info("99999")
        assert result is None

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_connection_error_returns_none(self, mock_client_cls):
        """Ошибка соединения возвращает None."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.RequestError("timeout", request=MagicMock())
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await get_track_info("12345")
        assert result is None

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_invalid_duration_type(self, mock_client_cls):
        """duration не int возвращает None."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"duration": "not_a_number"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await get_track_info("12345")
        assert result is None


class TestDownloadTrackStream:
    """Тесты download_track_stream."""

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_success(self, mock_client_cls):
        """Успешное скачивание стрима в файл."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            mock_resp = AsyncMock()
            mock_resp.raise_for_status = MagicMock()

            async def fake_aiter_bytes():
                yield b"chunk1"
                yield b"chunk2"

            mock_resp.aiter_bytes = fake_aiter_bytes

            mock_client = AsyncMock()
            mock_client.stream = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_resp),
                __aexit__=AsyncMock(return_value=False),
            ))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await download_track_stream("123", tmp_dir)
            assert result.endswith(".mp3")
            assert "123" in result


class TestDownloadCover:

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_success(self, mock_client_cls):
        """Успешное скачивание обложки."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            mock_response = MagicMock()
            mock_response.content = b"fake_image_bytes"
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await download_cover("123", tmp_dir)
            assert result.endswith(".jpg")
            assert os.path.exists(result)
            with open(result, "rb") as f:
                assert f.read() == b"fake_image_bytes"

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_error_returns_empty_string(self, mock_client_cls):
        """Ошибка возвращает пустую строку."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=Exception("Connection error")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await download_cover("123", "/tmp/test")
        assert result == ""

class TestTrimAudio:
    """Тесты trim_audio."""

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_success(self, mock_client_cls):
        """Успешная обрезка аудио."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Создаём фейковый исходный файл
            input_path = os.path.join(tmp_dir, "input.mp3")
            output_path = os.path.join(tmp_dir, "output.mp3")
            with open(input_path, "wb") as f:
                f.write(b"fake_audio")

            mock_response = MagicMock()
            mock_response.content = b"trimmed_audio_bytes"
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await trim_audio(input_path, 0, 60, output_path)
            assert result is True
            assert os.path.exists(output_path)

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_error_returns_false(self, mock_client_cls):
        """Ошибка HTTP возвращает False."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = os.path.join(tmp_dir, "input.mp3")
            output_path = os.path.join(tmp_dir, "output.mp3")
            with open(input_path, "wb") as f:
                f.write(b"fake_audio")

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Server error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await trim_audio(input_path, 0, 60, output_path)
            assert result is False


class TestCreateVideo:
    """Тесты create_video."""

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_success(self, mock_client_cls):
        """Успешное создание видео."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = os.path.join(tmp_dir, "audio.mp3")
            image_path = os.path.join(tmp_dir, "cover.jpg")
            output_path = os.path.join(tmp_dir, "video.mp4")

            with open(audio_path, "wb") as f:
                f.write(b"fake_audio")
            with open(image_path, "wb") as f:
                f.write(b"fake_image")

            mock_response = MagicMock()
            mock_response.content = b"fake_video_bytes"
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await create_video(audio_path, image_path, output_path)
            assert result is True
            assert os.path.exists(output_path)

    @patch("src.api_utils.httpx.AsyncClient")
    async def test_error_returns_false(self, mock_client_cls):
        """Ошибка возвращает False."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = os.path.join(tmp_dir, "audio.mp3")
            image_path = os.path.join(tmp_dir, "cover.jpg")
            output_path = os.path.join(tmp_dir, "video.mp4")

            with open(audio_path, "wb") as f:
                f.write(b"fake_audio")
            with open(image_path, "wb") as f:
                f.write(b"fake_image")

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await create_video(audio_path, image_path, output_path)
            assert result is False


class TestTrackInfoNamedTuple:
    """Тесты NamedTuple TrackInfo."""

    def test_create_track_info(self):
        """Создание TrackInfo."""
        t = TrackInfo(id=1, title="Song", artists="Artist", duration=180)
        assert t.id == 1
        assert t.title == "Song"
        assert t.artists == "Artist"
        assert t.duration == 180

    def test_track_info_immutable(self):
        """TrackInfo является неизменяемым."""
        t = TrackInfo(id=1, title="Song", artists="Artist", duration=180)
        with pytest.raises(AttributeError):
            t.id = 2
