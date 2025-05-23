import pytest
import io
from PIL import Image, ImageDraw
from pydub import AudioSegment
import numpy as np
from fastapi.testclient import TestClient # For synchronous client if needed
import httpx # For asynchronous client
import os

# Make sure the app path is recognized
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
async def async_client():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client


def create_dummy_image(width=100, height=100, color="blue", extension="png") -> io.BytesIO:
    """Creates a dummy image in memory."""
    img = Image.new("RGB", (width, height), color=color)
    # Add some detail to make it less likely to be identical if params change
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), f"{width}x{height}", fill="white")
    img_byte_arr = io.BytesIO()
    img_format = extension.upper()
    if img_format == "JPG":
        img_format = "JPEG"
    img.save(img_byte_arr, format=img_format)
    img_byte_arr.seek(0)
    return img_byte_arr


def create_dummy_audio(duration_ms=5000, channels=1, sample_rate=44100, extension="mp3") -> io.BytesIO:
    """Creates a dummy audio file in memory."""
    # Generate a simple sine wave
    num_samples = int(duration_ms / 1000 * sample_rate)
    t = np.linspace(0, duration_ms / 1000, num_samples, False)
    note = np.sin(440 * 2 * np.pi * t)  # 440 Hz tone
    audio_data = (note * 32767 / np.max(np.abs(note))).astype(np.int16)  # Normalize to 16-bit

    segment = AudioSegment(
        data=audio_data.tobytes(),
        sample_width=audio_data.dtype.itemsize,
        frame_rate=sample_rate,
        channels=channels
    )
    audio_byte_arr = io.BytesIO()
    segment.export(audio_byte_arr, format=extension)
    audio_byte_arr.seek(0)
    return audio_byte_arr


@pytest.fixture
def dummy_png_image_bytes() -> bytes:
    return create_dummy_image(extension="png").getvalue()


@pytest.fixture
def dummy_jpg_image_bytes() -> bytes:
    return create_dummy_image(extension="jpg").getvalue()


@pytest.fixture
def non_image_bytes() -> bytes:
    return b"this is not an image"


@pytest.fixture
def dummy_mp3_audio_bytes_5s() -> bytes:  # 5 seconds duration
    return create_dummy_audio(duration_ms=5000, extension="mp3").getvalue()


@pytest.fixture
def dummy_wav_audio_bytes_10s() -> bytes:  # 10 seconds duration
    return create_dummy_audio(duration_ms=10000, extension="wav").getvalue()


@pytest.fixture
def non_audio_bytes() -> bytes:
    return b"this is not audio"


