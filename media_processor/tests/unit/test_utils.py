# tests/unit/test_utils.py
import pytest
from fastapi import HTTPException, UploadFile
import io
from unittest.mock import MagicMock, AsyncMock # <--- IMPORT AsyncMock

from app.utils import (
    validate_image_content,
    validate_audio_content,
    validate_audio_range,
    validate_audio_duration
)
from pydub import AudioSegment

# --- Tests for validate_image_content ---
@pytest.mark.asyncio
async def test_validate_image_content_valid_png(dummy_png_image_bytes):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=dummy_png_image_bytes) # <--- USE AsyncMock
    content = await validate_image_content(mock_file)
    assert content == dummy_png_image_bytes

@pytest.mark.asyncio
async def test_validate_image_content_valid_jpg(dummy_jpg_image_bytes):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=dummy_jpg_image_bytes) # <--- USE AsyncMock
    content = await validate_image_content(mock_file)
    assert content == dummy_jpg_image_bytes

@pytest.mark.asyncio
async def test_validate_image_content_invalid(non_image_bytes):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=non_image_bytes) # <--- USE AsyncMock
    with pytest.raises(HTTPException) as exc_info:
        await validate_image_content(mock_file)
    assert exc_info.value.status_code == 400
    assert "Не удалось обработать файл как изображение" in exc_info.value.detail

# --- Tests for validate_audio_content ---
@pytest.mark.asyncio
async def test_validate_audio_content_valid_mp3(dummy_mp3_audio_bytes_5s):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=dummy_mp3_audio_bytes_5s) # <--- USE AsyncMock
    content = await validate_audio_content(mock_file)
    assert content == dummy_mp3_audio_bytes_5s

@pytest.mark.asyncio
async def test_validate_audio_content_valid_wav(dummy_wav_audio_bytes_10s):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=dummy_wav_audio_bytes_10s) # <--- USE AsyncMock
    content = await validate_audio_content(mock_file)
    assert content == dummy_wav_audio_bytes_10s

@pytest.mark.asyncio
async def test_validate_audio_content_invalid(non_audio_bytes):
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=non_audio_bytes) # <--- USE AsyncMock
    with pytest.raises(HTTPException) as exc_info:
        await validate_audio_content(mock_file)
    assert exc_info.value.status_code == 400
    assert "Файл не является поддерживаемым аудиоформатом" in exc_info.value.detail

# --- Tests for validate_audio_range ---
def test_validate_audio_range_valid():
    validate_audio_range(start=0, end=10)

def test_validate_audio_range_start_negative():
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_range(start=-1, end=10)
    assert exc_info.value.status_code == 400
    assert "Параметры времени не могут быть отрицательными" in exc_info.value.detail

def test_validate_audio_range_end_negative():
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_range(start=0, end=-5)
    assert exc_info.value.status_code == 400
    assert "Параметры времени не могут быть отрицательными" in exc_info.value.detail

def test_validate_audio_range_start_ge_end():
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_range(start=10, end=10)
    assert exc_info.value.status_code == 400
    assert "Параметр start должен быть меньше end" in exc_info.value.detail
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_range(start=11, end=10)
    assert exc_info.value.status_code == 400
    assert "Параметр start должен быть меньше end" in exc_info.value.detail

# --- Tests for validate_audio_duration ---
def test_validate_audio_duration_valid(dummy_mp3_audio_bytes_5s):
    validate_audio_duration(dummy_mp3_audio_bytes_5s, start=1, end=4)

def test_validate_audio_duration_start_exceeds(dummy_mp3_audio_bytes_5s):
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_duration(dummy_mp3_audio_bytes_5s, start=6, end=7)
    assert exc_info.value.status_code == 400
    assert "Параметры start и end не должны превышать длительность аудио" in exc_info.value.detail
    assert "(5.00 сек)" in exc_info.value.detail

def test_validate_audio_duration_end_exceeds(dummy_mp3_audio_bytes_5s):
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_duration(dummy_mp3_audio_bytes_5s, start=1, end=7)
    assert exc_info.value.status_code == 400
    assert "Параметры start и end не должны превышать длительность аудио" in exc_info.value.detail
    assert "(5.00 сек)" in exc_info.value.detail

def test_validate_audio_duration_bad_audio_content(non_audio_bytes):
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_duration(non_audio_bytes, start=1, end=2)
    assert exc_info.value.status_code == 400
    assert "Не удалось определить длительность аудио" in exc_info.value.detail