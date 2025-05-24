import pytest
from httpx import AsyncClient
import io
from urllib.parse import unquote_plus

from tests.conftest import create_dummy_audio, create_dummy_image  # Import helpers
from pydub import AudioSegment  # For checking trimmed audio


# --- Tests for /trim_audio endpoint ---

@pytest.mark.asyncio
async def test_trim_audio_endpoint_success(async_client: AsyncClient):
    audio_content_io = create_dummy_audio(duration_ms=10000, extension="mp3")  # 10s audio
    files = {'file': ('test_audio.mp3', audio_content_io, 'audio/mpeg')}
    data = {'start': '2', 'end': '5'}  # Trim from 2s to 5s

    response = await async_client.post("/trim_audio", files=files, data=data)

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"

    filename = unquote_plus(response.headers["content-disposition"].split("filename*=UTF-8''")[1])
    assert filename == "cut_test_audio_2_5.mp3"

    trimmed_audio_bytes = response.content
    assert len(trimmed_audio_bytes) > 0

    # Verify duration of the trimmed audio
    trimmed_segment = AudioSegment.from_file(io.BytesIO(trimmed_audio_bytes), format="mp3")
    expected_duration_ms = (5 - 2) * 1000
    assert abs(len(trimmed_segment) - expected_duration_ms) < 200  # Allow 200ms tolerance


@pytest.mark.asyncio
async def test_trim_audio_endpoint_invalid_range(async_client: AsyncClient):
    audio_content_io = create_dummy_audio(duration_ms=5000, extension="mp3")
    files = {'file': ('test.mp3', audio_content_io, 'audio/mpeg')}
    data = {'start': '3', 'end': '1'}  # start > end

    response = await async_client.post("/trim_audio", files=files, data=data)
    assert response.status_code == 400
    json_response = response.json()
    assert "Параметр start должен быть меньше end" in json_response["detail"]


@pytest.mark.asyncio
async def test_trim_audio_endpoint_duration_exceeded(async_client: AsyncClient):
    audio_content_io = create_dummy_audio(duration_ms=3000, extension="mp3")  # 3s audio
    files = {'file': ('short_audio.mp3', audio_content_io, 'audio/mpeg')}
    data = {'start': '1', 'end': '5'}  # end (5s) > duration (3s)

    response = await async_client.post("/trim_audio", files=files, data=data)
    assert response.status_code == 400
    json_response = response.json()
    assert "Параметры start и end не должны превышать длительность аудио" in json_response["detail"]
    assert "(3.00 сек)" in json_response["detail"]


@pytest.mark.asyncio
async def test_trim_audio_endpoint_not_audio_file(async_client: AsyncClient):
    not_audio_content_io = io.BytesIO(b"this is plain text")
    files = {'file': ('not_audio.txt', not_audio_content_io, 'text/plain')}
    data = {'start': '0', 'end': '1'}

    response = await async_client.post("/trim_audio", files=files, data=data)
    assert response.status_code == 400
    json_response = response.json()
    assert "Файл не является поддерживаемым аудиоформатом" in json_response["detail"]


# --- Tests for /create_video endpoint ---

@pytest.mark.asyncio
async def test_create_video_endpoint_success(async_client: AsyncClient):
    audio_content_io = create_dummy_audio(duration_ms=2000, extension="mp3")  # 2s audio
    image_content_io = create_dummy_image(width=640, height=480, extension="png")

    files = {
        'audio_file': ('my_sound.mp3', audio_content_io, 'audio/mpeg'),
        'image_file': ('my_cover.png', image_content_io, 'image/png')
    }

    response = await async_client.post("/create_video", files=files)

    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"

    filename = unquote_plus(response.headers["content-disposition"].split("filename*=UTF-8''")[1])
    assert filename == "my_sound_with_cover_my_cover.mp4"

    video_bytes = response.content
    assert len(video_bytes) > 1000  # Arbitrary check for non-empty video
    # A simple check for MP4-like structure. This isn't a full validation.
    assert b'ftypmp42' in video_bytes[:100] or b'ftypisom' in video_bytes[:100] or b'moov' in video_bytes[:500]


@pytest.mark.asyncio
async def test_create_video_endpoint_invalid_audio(async_client: AsyncClient):
    not_audio_content_io = io.BytesIO(b"this is not audio at all")
    image_content_io = create_dummy_image(width=100, height=100, extension="jpeg")

    files = {
        'audio_file': ('bad_audio.txt', not_audio_content_io, 'text/plain'),
        'image_file': ('cover.jpg', image_content_io, 'image/jpeg')
    }

    response = await async_client.post("/create_video", files=files)
    assert response.status_code == 400
    json_response = response.json()
    assert "Файл не является поддерживаемым аудиоформатом" in json_response["detail"]


@pytest.mark.asyncio
async def test_create_video_endpoint_invalid_image(async_client: AsyncClient):
    audio_content_io = create_dummy_audio(duration_ms=1000, extension="wav")
    not_image_content_io = io.BytesIO(b"this is not an image at all")

    files = {
        'audio_file': ('sound.wav', audio_content_io, 'audio/wav'),
        'image_file': ('bad_image.txt', not_image_content_io, 'text/plain')
    }

    response = await async_client.post("/create_video", files=files)
    assert response.status_code == 400
    json_response = response.json()
    assert "Не удалось обработать файл как изображение" in json_response["detail"]