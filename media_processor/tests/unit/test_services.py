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

    def create_fake_output_files_correctly(stream, **kwargs):
        """
        Надежно находит имя выходного файла и имитирует его создание.
        """
        # stream.get_args() возвращает всю команду в виде списка.
        # Имя выходного файла - это последний позиционный аргумент.
        args = stream.get_args()
        
        # Ищем последний аргумент, который выглядит как путь к файлу
        # (не начинается с '-' и содержит расширение)
        output_filename = None
        for arg in reversed(args):
            if not arg.startswith('-') and ('/' in arg or '\\' in arg):
                output_filename = arg
                break
        
        if not output_filename:
            raise ValueError(f"Не удалось найти имя выходного файла в аргументах ffmpeg: {args}")

        if output_filename.endswith('.mp4'):
            content = b"fake_video_bytes_moov"
        else:
            content = b""

        with open(output_filename, "wb") as f:
            f.write(content)

    mock_ffmpeg_run.side_effect = create_fake_output_files_correctly

    # Запускаем тест
    video_bytes = create_video_from_audio_and_cover_files(audio_file_io, image_file_io)

    # Проверяем результат
    assert video_bytes == b"fake_video_bytes_moov"
    assert mock_ffmpeg_run.call_count == 2

    # Используем tempfile.gettempdir() без realpath чтобы соответствовать коду в services.py
    temp_dir = tempfile.gettempdir()

    # Проверяем что probe был вызван с файлом содержащим нужную часть пути
    mock_ffmpeg_probe.assert_called_once()
    probe_call_arg = mock_ffmpeg_probe.call_args[0][0]
    assert 'tmp_audio_converted_uuid-audio-conv.aac' in probe_call_arg

    # Проверяем что remove был вызван для временных файлов
    assert mock_os_remove.call_count == 4


def test_create_video_integration():
    audio_file_io = create_dummy_audio(duration_ms=2000, extension="mp3")
    image_file_io = create_dummy_image(width=1280, height=720, extension="png")

    video_bytes = create_video_from_audio_and_cover_files(audio_file_io, image_file_io)

    assert video_bytes is not None
    assert len(video_bytes) > 0
    assert b'ftypmp42' in video_bytes[:100] or b'moov' in video_bytes

@pytest.mark.asyncio
async def test_trim_audio_exception_handling(non_audio_bytes):
    """Тестирует обработку исключений внутри trim_audio."""
    # non_audio_bytes берется из фикстуры в conftest.py
    trimmed_buffer = await trim_audio(non_audio_bytes, 0, 5)

    # Проверяем, что возвращен пустой буфер (0 байт)
    assert trimmed_buffer.getbuffer().nbytes == 0


def test_crop_to_square_small_image_no_resize():
    """Тестирует, что небольшое изображение 
    не будет увеличено, а только обрезано до квадрата.
    """
    # Создаем изображение 400x300. Меньшая сторона = 300 (< 640)
    image_bytes_io = create_dummy_image(width=400, height=300, extension="png")
    cropped_buffer = crop_to_square(image_bytes_io)
    cropped_buffer.seek(0)
    img = Image.open(cropped_buffer)
    assert img.width == 300
    assert img.height == 300
    assert img.format == "PNG"


def test_crop_to_square_exception_handling(non_image_bytes):
    """Тестирует обработку исключений внутри crop_to_square."""
    # Оборачиваем невалидные байты из conftest.py в BytesIO, т.к. функция ожидает BinaryIO
    invalid_io = io.BytesIO(non_image_bytes)
    cropped_buffer = crop_to_square(invalid_io)
    # Проверяем, что возвращен пустой буфер (0 байт)
    assert cropped_buffer.getbuffer().nbytes == 0
