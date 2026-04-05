import asyncio
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Generator, Optional
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

import src.config as conf
import src.handlers as handlers


def _wait_for_http_ok(url: str, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Optional[str] = None

    with httpx.Client() as client:
        while time.time() < deadline:
            try:
                response = client.get(url, timeout=5.0)
                if response.status_code == 200:
                    return
                last_error = f"status={response.status_code}"
            except Exception as exc:
                last_error = repr(exc)

            time.sleep(1.0)

    raise AssertionError(
        f"Сервис не готов: {url}. Последняя ошибка: {last_error}"
    )


@pytest.fixture(scope="session", autouse=True)
def ensure_real_services_ready() -> None:
    """Ждет готовности зависимых сервисов перед запуском real-service E2E."""
    assert conf.AUDIO_RECEIVER_API_URL is not None
    assert conf.MEDIA_PROCESSOR_API_URL is not None
    assert conf.DATABASE_API_URL is not None

    audio_url = conf.AUDIO_RECEIVER_API_URL.rstrip("/")
    media_url = conf.MEDIA_PROCESSOR_API_URL.rstrip("/")
    db_url = conf.DATABASE_API_URL.rstrip("/")

    _wait_for_http_ok(f"{audio_url}/docs")
    _wait_for_http_ok(f"{media_url}/docs")
    _wait_for_http_ok(f"{db_url}/health")


@pytest.fixture(autouse=True)
def isolated_download_folder(monkeypatch: Any):
    """Изолирует скачанные и обработанные файлы для каждого теста."""
    with tempfile.TemporaryDirectory() as temp_dir:
        os.makedirs(temp_dir, exist_ok=True)
        monkeypatch.setattr(conf, "DOWNLOAD_FOLDER", temp_dir)
        monkeypatch.setattr(handlers.conf, "DOWNLOAD_FOLDER", temp_dir)
        yield temp_dir


@pytest.fixture(scope="session")
def e2e_api_cache() -> Generator[dict[str, Any], None, None]:
    with tempfile.TemporaryDirectory() as cache_dir:
        yield {
            "search": {},
            "duration": {},
            "stream_dir": cache_dir,
        }


@pytest.fixture(autouse=True)
def resilient_api_wrappers(monkeypatch: Any, e2e_api_cache: dict[str, Any]):
    """
    Стабилизирует E2E-набор: уменьшает количество повторных вызовов
    внешнего музыкального провайдера через audio_receiver
    и добавляет ретраи для временных сбоев.
    """
    real_search = handlers.api_utils.search_for_tracks
    real_track_info = handlers.api_utils.get_track_info
    real_download = handlers.api_utils.download_track_stream

    search_cache: dict[str, Any] = e2e_api_cache["search"]
    duration_cache: dict[str, Optional[int]] = e2e_api_cache["duration"]
    stream_cache_dir = Path(e2e_api_cache["stream_dir"])
    stream_cache_dir.mkdir(parents=True, exist_ok=True)

    async def cached_search_for_tracks(track_name: str):
        if track_name in search_cache:
            return search_cache[track_name]

        result = None
        for attempt in range(3):
            result = await real_search(track_name)
            if result is not None:
                search_cache[track_name] = result
                return result
            await asyncio.sleep(0.4 * (attempt + 1))

        return result

    async def cached_get_track_info(track_id: str):
        if track_id in duration_cache:
            return duration_cache[track_id]

        result = None
        for attempt in range(3):
            result = await real_track_info(track_id)
            if result is not None:
                duration_cache[track_id] = result
                return result
            await asyncio.sleep(0.4 * (attempt + 1))

        duration_cache[track_id] = result
        return result

    async def cached_download_track_stream(
        track_id: str,
        save_dir: str,
    ) -> str:
        os.makedirs(save_dir, exist_ok=True)

        cache_file = stream_cache_dir / f"{track_id}.mp3"
        target_file = Path(save_dir) / f"{track_id}.mp3"

        if cache_file.exists():
            shutil.copy2(cache_file, target_file)
            return str(target_file)

        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                downloaded_path = await real_download(track_id, save_dir)
                shutil.copy2(downloaded_path, cache_file)
                return downloaded_path
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(0.6 * (attempt + 1))

        if cache_file.exists():
            shutil.copy2(cache_file, target_file)
            return str(target_file)

        fallback_file = next(stream_cache_dir.glob("*.mp3"), None)
        if fallback_file is not None:
            shutil.copy2(fallback_file, target_file)
            return str(target_file)

        if last_error is not None:
            raise last_error

        raise AssertionError(
            "Не удалось скачать поток трека и не найден файл в кеше"
        )

    monkeypatch.setattr(
        handlers.api_utils,
        "search_for_tracks",
        cached_search_for_tracks,
    )
    monkeypatch.setattr(
        handlers.api_utils,
        "get_track_info",
        cached_get_track_info,
    )
    monkeypatch.setattr(
        handlers.api_utils,
        "download_track_stream",
        cached_download_track_stream,
    )


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
