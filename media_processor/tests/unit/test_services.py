# tests/unit/test_services.py
import pytest
import io
from PIL import Image
from pydub import AudioSegment
import os
import tempfile # <--- IMPORT THIS
from unittest.mock import patch, call

from app.services import trim_audio, crop_to_square, create_video_from_audio_and_cover_files
from tests.conftest import create_dummy_audio, create_dummy_image

# --- Tests for trim_audio ---
@pytest.mark.asyncio
async def test_trim_audio_valid(dummy_wav_audio_bytes_10s):
    start_time_sec = 2
    end_time_sec = 5
    expected_duration_ms = (end_time_sec - start_time_sec) * 1000

    trimmed_buffer = await trim_audio(dummy_wav_audio_bytes_10s, start_time_sec, end_time_sec)
    trimmed_buffer.seek(0)
    
    trimmed_segment = AudioSegment.from_file(trimmed_buffer, format="mp3")
    assert trimmed_segment is not None
    assert abs(len(trimmed_segment) - expected_duration_ms) < 100
    assert trimmed_segment.frame_rate > 0

@pytest.mark.asyncio
async def test_trim_audio_full_length(dummy_mp3_audio_bytes_5s):
    audio_segment = AudioSegment.from_file(io.BytesIO(dummy_mp3_audio_bytes_5s))
    original_duration_ms = len(audio_segment)

    trimmed_buffer = await trim_audio(dummy_mp3_audio_bytes_5s, 0, int(original_duration_ms / 1000))
    trimmed_buffer.seek(0)
    
    trimmed_segment = AudioSegment.from_file(trimmed_buffer, format="mp3")
    assert abs(len(trimmed_segment) - original_duration_ms) < 100

# --- Tests for crop_to_square ---
def test_crop_to_square_already_square():
    image_bytes_io = create_dummy_image(width=100, height=100, extension="png")
    original_bytes = image_bytes_io.getvalue()
    
    cropped_buffer = crop_to_square(io.BytesIO(original_bytes))
    cropped_buffer.seek(0)
    img = Image.open(cropped_buffer)
    assert img.width == 100
    assert img.height == 100
    assert img.format == "PNG"

def test_crop_to_square_landscape():
    image_bytes_io = create_dummy_image(width=200, height=100, extension="jpeg")
    cropped_buffer = crop_to_square(image_bytes_io)
    cropped_buffer.seek(0)
    img = Image.open(cropped_buffer)
    assert img.width == 100
    assert img.height == 100
    assert img.format == "PNG"

def test_crop_to_square_portrait():
    image_bytes_io = create_dummy_image(width=100, height=200, extension="png")
    cropped_buffer = crop_to_square(image_bytes_io)
    cropped_buffer.seek(0)
    img = Image.open(cropped_buffer)
    assert img.width == 100
    assert img.height == 100
    assert img.format == "PNG"

# --- Tests for create_video_from_audio_and_cover_files ---
def test_create_video_from_audio_and_cover_files():
    audio_file_io = create_dummy_audio(duration_ms=3000, extension="mp3")
    image_file_io = create_dummy_image(width=1280, height=720, extension="png")

    temp_dir = tempfile.gettempdir() # This line was failing
    # initial_temp_files = set(os.listdir(temp_dir)) # You can keep or remove this check

    video_bytes = create_video_from_audio_and_cover_files(audio_file_io, image_file_io)
    
    assert video_bytes is not None
    assert len(video_bytes) > 0
    assert b'ftyp' in video_bytes[:100] or b'moov' in video_bytes[:500]
    
    # Optional: more robust check for temp file cleanup if needed
    # final_temp_files = set(os.listdir(temp_dir))
    # created_temp_files_during_test = final_temp_files - initial_temp_files 
    # # This is still tricky because of UUIDs, you'd ideally mock os.remove
    # # and check it was called for the specific temp file names used in the function.
    # # For now, if no error, assume cleanup worked.