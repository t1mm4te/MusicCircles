# tests/unit/test_services.py
import pytest
import io
from PIL import Image
from pydub import AudioSegment
import os
import uuid
import tempfile 
from unittest.mock import patch, ANY, call

# Импортируем тестируемые функции
from app.services import trim_audio, crop_to_square, create_video_from_audio_and_cover_files
# Импортируем фикстуры и хелперы для создания тестовых данных
from tests.conftest import create_dummy_audio, create_dummy_image, dummy_wav_audio_bytes_10s, dummy_mp3_audio_bytes_5s

# --- Тесты для trim_audio ---

@pytest.mark.asyncio
async def test_trim_audio_valid(dummy_wav_audio_bytes_10s):
    start_time_sec = 2
    end_time_sec = 5
    expected_duration_ms = (end_time_sec - start_time_sec) * 1000

    trimmed_buffer = await trim_audio(dummy_wav_audio_bytes_10s, start_time_sec, end_time_sec)
    trimmed_buffer.seek(0)
    
    # Убедимся, что буфер не пустой
    assert trimmed_buffer.getbuffer().nbytes > 0
    
    trimmed_segment = AudioSegment.from_file(trimmed_buffer, format="mp3")
    assert trimmed_segment is not None
    # Проверяем длительность с небольшой погрешностью из-за особенностей кодирования
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

# --- Тесты для crop_to_square ---

def test_crop_to_square_already_square():
    image_bytes_io = create_dummy_image(width=100, height=100, extension="png")
    
    cropped_buffer = crop_to_square(image_bytes_io)
    cropped_buffer.seek(0)
    img = Image.open(cropped_buffer)

    assert img.width == 100
    assert img.height == 100
    assert img.format == "PNG" # Функция сохраняет в PNG

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

def test_crop_to_square_resizes_large_image():
    # Тестируем, что изображение > 640px будет уменьшено до 640x640
    image_bytes_io = create_dummy_image(width=1000, height=800, extension="png")

    cropped_buffer = crop_to_square(image_bytes_io)
    cropped_buffer.seek(0)
    img = Image.open(cropped_buffer)

    assert img.width == 640
    assert img.height == 640
    assert img.format == "PNG"

# --- Тесты для create_video_from_audio_and_cover_files ---
@patch('app.services.ffmpeg.probe')
@patch('app.services.os.remove')
@patch('app.services.ffmpeg.run')
@patch('app.services.uuid.uuid4', side_effect=['uuid-audio', 'uuid-audio-conv', 'uuid-image', 'uuid-video'])
def test_create_video_mocked(
    mock_uuid,
    mock_ffmpeg_run,
    mock_os_remove,
    mock_ffmpeg_probe
):
    """Более "чистый" юнит-тест с моками, который не запускает ffmpeg."""
    audio_file_io = create_dummy_audio(duration_ms=3000)
    image_file_io = create_dummy_image(width=800, height=600)

    mock_ffmpeg_probe.return_value = {'format': {'duration': '3.00'}}

    # ФИНАЛЬНЫЙ, ИСПРАВЛЕННЫЙ МОК
    def create_fake_output_files_correctly(stream, **kwargs):
        """
        Надежно находит имя выходного файла и имитирует его создание.
        """
        # stream.get_args() возвращает всю команду в виде списка.
        # Имя выходного файла - это один из последних аргументов, но не всегда самый последний.
        # Он передается в ffmpeg.output() как позиционный аргумент.
        # В данном случае, это один из аргументов, который не начинается с '-'.
        # Давайте найдем его.
        args = stream.get_args()
        
        # Надежный способ: ищем аргумент, который является абсолютным путем и заканчивается на наше расширение.
        # Это будет работать для .aac и .mp4
        output_filename = None
        for arg in reversed(args):
            if arg.startswith('/tmp/') and (arg.endswith('.aac') or arg.endswith('.mp4')):
                output_filename = arg
                break
        
        if not output_filename:
            # Если не нашли, это неожиданно, уроним тест, чтобы понять почему.
            raise ValueError(f"Не удалось найти имя выходного файла в аргументах ffmpeg: {args}")

        if output_filename.endswith('.mp4'):
            content = b"fake_video_bytes_moov"
        else:
            content = b""

        with open(output_filename, "wb") as f:
            f.write(content)

    mock_ffmpeg_run.side_effect = create_fake_output_files_correctly

    # Запускаем тест (уже без отладочных print)
    video_bytes = create_video_from_audio_and_cover_files(audio_file_io, image_file_io)

    # Проверяем результат
    assert video_bytes == b"fake_video_bytes_moov"
    assert mock_ffmpeg_run.call_count == 2
    
    # ... остальные проверки ...
    temp_dir = os.path.realpath(tempfile.gettempdir())
    expected_audio_conv_file = os.path.join(temp_dir, 'tmp_audio_converted_uuid-audio-conv.aac')
    mock_ffmpeg_probe.assert_called_once_with(expected_audio_conv_file)

    expected_files_to_remove = [
        os.path.join(temp_dir, 'tmp_audio_uuid-audio.aac'),
        os.path.join(temp_dir, 'tmp_audio_converted_uuid-audio-conv.aac'),
        os.path.join(temp_dir, 'tmp_image_uuid-image.png'),
        os.path.join(temp_dir, 'tmp_video_uuid-video.mp4')
    ]
    mock_os_remove.assert_has_calls([call(f) for f in expected_files_to_remove], any_order=True)

# Оставляем и оригинальный интеграционный тест, он тоже полезен
def test_create_video_integration():
    """Интеграционный тест, который реально запускает ffmpeg. 
    Он медленный, но проверяет реальную работу с ffmpeg."""
    audio_file_io = create_dummy_audio(duration_ms=2000, extension="mp3")
    image_file_io = create_dummy_image(width=1280, height=720, extension="png")

    video_bytes = create_video_from_audio_and_cover_files(audio_file_io, image_file_io)
    
    assert video_bytes is not None
    assert len(video_bytes) > 0
    # Простой, но эффективный способ проверить, что это похоже на mp4 файл
    # 'ftyp' обычно в начале, 'moov' (movie atom) должен быть где-то в файле
    assert b'ftypmp42' in video_bytes[:100] or b'moov' in video_bytes