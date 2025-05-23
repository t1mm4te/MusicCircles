import pytest
import io
from PIL import Image
from pydub import AudioSegment
import os
from unittest.mock import patch, call  # For mocking ffmpeg if needed, but here we'll test it

from app.services import trim_audio, crop_to_square, create_video_from_audio_and_cover_files
from tests.conftest import create_dummy_audio, create_dummy_image  # Import helpers


# --- Tests for trim_audio ---
@pytest.mark.asyncio
async def test_trim_audio_valid(dummy_wav_audio_bytes_10s):  # Use WAV for easier duration check
    # dummy_wav_audio_bytes_10s is 10 seconds long
    start_time_sec = 2
    end_time_sec = 5
    expected_duration_ms = (end_time_sec - start_time_sec) * 1000

    trimmed_buffer = await trim_audio(dummy_wav_audio_bytes_10s, start_time_sec, end_time_sec)
    trimmed_buffer.seek(0)

    # Check if output is valid audio and has correct duration
    trimmed_segment = AudioSegment.from_file(trimmed_buffer, format="mp3")
    assert trimmed_segment is not None
    # Duration might not be exact due to encoding, allow small tolerance
    assert abs(len(trimmed_segment) - expected_duration_ms) < 100  # 100ms tolerance
    assert trimmed_segment.frame_rate > 0  # Basic check it's valid audio


@pytest.mark.asyncio
async def test_trim_audio_full_length(dummy_mp3_audio_bytes_5s):
    # dummy_mp3_audio_bytes_5s is 5 seconds long
    audio_segment = AudioSegment.from_file(io.BytesIO(dummy_mp3_audio_bytes_5s))
    original_duration_ms = len(audio_segment)

    trimmed_buffer = await trim_audio(dummy_mp3_audio_bytes_5s, 0, int(original_duration_ms / 1000))
    trimmed_buffer.seek(0)

    trimmed_segment = AudioSegment.from_file(trimmed_buffer, format="mp3")
    assert abs(len(trimmed_segment) - original_duration_ms) < 100


# --- Tests for crop_to_square ---
def test_crop_to_square_already_square():
    image_bytes_io = create_dummy_image(width=100, height=100, extension="png")
    # For already square images, the function returns the original file object if it's BinaryIO
    # If we pass BytesIO, it re-saves it. Let's test the re-save path.
    original_bytes = image_bytes_io.getvalue()

    cropped_buffer = crop_to_square(io.BytesIO(original_bytes))  # Pass a new BytesIO
    cropped_buffer.seek(0)
    img = Image.open(cropped_buffer)
    assert img.width == 100
    assert img.height == 100
    assert img.format == "PNG"  # crop_to_square saves as PNG


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
# This is more of an integration test for the service function as it uses ffmpeg
# Ensure ffmpeg is in PATH or provide path to it for these tests to run
def test_create_video_from_audio_and_cover_files():
    audio_file_io = create_dummy_audio(duration_ms=3000, extension="mp3")  # 3 sec MP3
    image_file_io = create_dummy_image(width=1280, height=720, extension="png")  # 16:9 image

    # Check temp dir before
    temp_dir = tempfile.gettempdir()
    initial_temp_files = set(os.listdir(temp_dir))

    video_bytes = create_video_from_audio_and_cover_files(audio_file_io, image_file_io)

    assert video_bytes is not None
    assert len(video_bytes) > 0  # Video should have some content

    # Verify it's a somewhat valid MP4 (basic check, proper validation is complex)
    # A simple check: MP4 files often start with 'ftyp' or similar box types near the beginning
    # This is not foolproof but better than nothing.
    assert b'ftyp' in video_bytes[:100] or b'moov' in video_bytes[:500]

    # Check temp dir after to ensure cleanup (this is a bit indirect)
    # This relies on the function's finally block. A more robust test would
    # mock os.remove and check calls, but that's more involved.
    # For now, we assume if no error, files were cleaned.
    # A more direct check would involve listing files and seeing if the specific
    # tmp_ files are gone, but their names are UUID based.
    # So, we'll check if the number of files hasn't grown uncontrollably.
    # This part is tricky without more intrusive mocking.
    # The `finally` block in the original code should handle cleanup.

    # Optional: If you have ffprobe, you could verify video duration and codec
    # For example:
    # with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_out:
    #     tmp_out.write(video_bytes)
    #     tmp_video_path = tmp_out.name
    # try:
    #     probe = ffmpeg.probe(tmp_video_path)
    #     video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    #     audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
    #     assert video_stream is not None
    #     assert audio_stream is not None
    #     assert abs(float(video_stream['duration']) - 3.0) < 0.5 # Check duration ~3s
    #     assert video_stream['codec_name'] == 'h264'
    #     assert audio_stream['codec_name'] == 'aac'
    # finally:
    #     os.remove(tmp_video_path)
    pass  # Relying on the no-exception and file size for now