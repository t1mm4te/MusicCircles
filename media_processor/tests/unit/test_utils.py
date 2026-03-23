import pytest
from fastapi import HTTPException, UploadFile
import io
from unittest.mock import MagicMock, AsyncMock

from app.utils import (
    validate_image_content,
    validate_audio_content,
    validate_audio_range,
    validate_audio_duration
)
from pydub import AudioSegment


# Tests for validate_image_content
# Проверка - загруженный файл является картинкой?
@pytest.mark.asyncio
async def test_validate_image_content_valid_png(dummy_png_image_bytes):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=dummy_png_image_bytes)
    content = await validate_image_content(mock_file)
    assert content == dummy_png_image_bytes


@pytest.mark.asyncio
async def test_validate_image_content_valid_jpg(dummy_jpg_image_bytes):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=dummy_jpg_image_bytes)
    content = await validate_image_content(mock_file)
    assert content == dummy_jpg_image_bytes


# Проверка падения при не валидных данных
@pytest.mark.asyncio
async def test_validate_image_content_invalid(non_image_bytes):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=non_image_bytes)
    with pytest.raises(HTTPException) as exc_info:
        await validate_image_content(mock_file)
    assert exc_info.value.status_code == 400
    assert "Не удалось обработать файл как изображение" in exc_info.value.detail


# Tests for validate_audio_content
# Проверка - загруженный файл является аудио файлом?
@pytest.mark.asyncio
async def test_validate_audio_content_valid_mp3(dummy_audio_bytes_80s):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=dummy_audio_bytes_80s)
    content = await validate_audio_content(mock_file)
    assert content == dummy_audio_bytes_80s


@pytest.mark.asyncio
async def test_validate_audio_content_valid_wav(dummy_wav_audio_bytes_80s):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=dummy_wav_audio_bytes_80s)
    content = await validate_audio_content(mock_file)
    assert content == dummy_wav_audio_bytes_80s


@pytest.mark.asyncio
async def test_validate_audio_content_invalid(non_audio_bytes):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=non_audio_bytes)
    with pytest.raises(HTTPException) as exc_info:
        await validate_audio_content(mock_file)
    assert exc_info.value.status_code == 400
    assert "Файл не является поддерживаемым аудиоформатом" in exc_info.value.detail


# Tests for validate_audio_range
@pytest.mark.parametrize("start, end", [
    (0, 54),  # Внутри границы
    (10, 65), # Ровно на границе
    (0, 10),
])
def test_validate_audio_range_success(start, end):
    validate_audio_range(start=start, end=end)


@pytest.mark.parametrize("start, end, expected_error", [
    (0, 56, "Длительность фрагмента не может превышать 55 секунд"),
    (-1, 10, "Параметры времени не могут быть отрицательными"),
    (0, -5, "Параметры времени не могут быть отрицательными"),
    (10, 10, "Параметр start должен быть меньше end"),
    (11, 10, "Параметр start должен быть меньше end")
])
def test_validate_audio_range_errors(start, end, expected_error):
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_range(start=start, end=end)
    assert exc_info.value.status_code == 400
    assert expected_error in exc_info.value.detail


# Tests for validate_audio_duration
@pytest.mark.parametrize("start, end", [
    (1, 80),
    (0, 50),
    (15, 60),
])
def test_validate_audio_duration_success(dummy_audio_bytes_80s, start, end):
    validate_audio_duration(dummy_audio_bytes_80s, start=start, end=end)


@pytest.mark.parametrize("start, end", [
    (81, 85),
    (70, 90),
    (10, 100)
])
def test_validate_audio_duration_errors(dummy_audio_bytes_80s, start, end):
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_duration(dummy_audio_bytes_80s, start=start, end=end)
    assert exc_info.value.status_code == 400
    assert "не должны превышать длительность аудио" in exc_info.value.detail
    assert "(80.00 сек)" in exc_info.value.detail


def test_validate_audio_duration_bad_audio_content(non_audio_bytes):
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_duration(non_audio_bytes, start=1, end=2)
    assert exc_info.value.status_code == 400
    assert "Не удалось определить длительность аудио" in exc_info.value.detail
