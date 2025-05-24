
import io
import os
import ffmpeg
import tempfile
from typing import BinaryIO
import uuid
from PIL import Image
from pydub import AudioSegment

async def trim_audio(audio_file: bytes, start_time: int, end_time: int) -> io.BytesIO:
    """
    Обрезает аудиофайл до заданного временного отрезка.

    Args:
        audio_file: Байты аудиофайла.
        start_time: Начало отрезка в секундах.
        end_time: Конец отрезка в секундах.

    Returns:
        io.BytesIO: Объект, содержащий обрезанный аудиофайл в формате MP3.
    """
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_file))
        start_ms = start_time * 1000
        end_ms = end_time * 1000
        trimmed_audio = audio[start_ms:end_ms]
        output_buffer = io.BytesIO()
        trimmed_audio.export(output_buffer, format="mp3")
        output_buffer.seek(0)
        return output_buffer
    except Exception as e:
        print(f"Ошибка при обработке аудио: {e}")
        return io.BytesIO()


def crop_to_square(image_file: BinaryIO) -> io.BytesIO:
    """
    Обрезает изображение до квадратной формы по центру и по меньшей стороне.

    Args:
        image_file: Байты файла изображения.

    Returns:
        io.BytesIO: Объект, содержащий обрезанное изображение в формате PNG.
    """
    try:
        img = Image.open(image_file)
        width, height = img.size

        # if width == height:
        #     return image_file  # Изображение уже квадратное

        min_side = min(width, height)
        left = (width - min_side) // 2
        top = (height - min_side) // 2
        right = (width + min_side) // 2
        bottom = (height + min_side) // 2

        cropped_img = img.crop((left, top, right, bottom))
        if min_side > 640:
            cropped_img = cropped_img.resize((640, 640), Image.LANCZOS)
        output_buffer = io.BytesIO()
        cropped_img.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        return output_buffer
    except Exception as e:
        print(f"Ошибка при обработке изображения: {e}")
        return io.BytesIO()


def create_video_from_audio_and_cover_files(audio_file: BinaryIO, image_file: BinaryIO) -> bytes:
    """
    Создание видео из аудио и обложки

    Args:
        audio_file: Загружаемый аудиофайл.
        image_file: Загружаемый файл с изображением.

    Returns:
        video_bytes: Видео в байтах.
    """
    audio_suffix = ".aac"
    audio_converted_suffix = ".aac"
    image_suffix = ".png"
    video_suffix = ".mp4"

    tmp_audio_name = os.path.join(tempfile.gettempdir(), f"tmp_audio_{uuid.uuid4()}{audio_suffix}")
    tmp_audio_converted_name = os.path.join(tempfile.gettempdir(), f"tmp_audio_converted_{uuid.uuid4()}{audio_converted_suffix}")
    tmp_image_name = os.path.join(tempfile.gettempdir(), f"tmp_image_{uuid.uuid4()}{image_suffix}")
    tmp_video_name = os.path.join(tempfile.gettempdir(), f"tmp_video_{uuid.uuid4()}{video_suffix}")

    try:
        # Сохраняем исходные файлы
        with open(tmp_audio_name, "wb") as f:
            f.write(audio_file.read())

        cropped_image_buffer = crop_to_square(image_file)
        with open(tmp_image_name, "wb") as f:
            f.write(cropped_image_buffer.read())

        # Перекодируем аудио в AAC-LC с нормализацией частоты и каналов
        audio_stream = ffmpeg.input(tmp_audio_name)
        audio_out = ffmpeg.output(
            audio_stream,
            tmp_audio_converted_name,
            acodec='aac',
            ar='44100',
            ac='2',
            strict='experimental'
        )
        try:
            ffmpeg.run(audio_out, capture_stderr=True, quiet=False)
        except ffmpeg.Error as e:
            print("Ошибка при перекодировании аудио:")
            print(e.stderr.decode('utf8'))
            raise

        # Входы для видео и аудио
        image_stream = ffmpeg.input(tmp_image_name, loop=1, framerate=25)
        # Масштабируем изображение к четным размерам
        scaled_image_stream = image_stream.filter('scale', 'ceil(iw/2)*2', 'ceil(ih/2)*2')
        audio_input_stream = ffmpeg.input(tmp_audio_converted_name)

        # Добавляем аудио фильтр для синхронизации, если перекодировать аудио:
        # audio_filtered = audio_input_stream.filter('aresample', async=1)
        # Но тут мы копируем аудио (acodec='copy'), поэтому не фильтруем.
        duration_info = ffmpeg.probe(tmp_audio_converted_name)
        duration = float(duration_info['format']['duration'])
        duration = min(55, duration)

        output_stream = ffmpeg.output(
            scaled_image_stream,
            audio_input_stream,
            tmp_video_name,
            vcodec='libx264',
            acodec='copy',       # копируем аудио
            pix_fmt='yuv420p',
            vsync='cfr',         # фиксированный FPS
            t=duration,              # ограничиваем длину видео 55 сек (если надо)
            movflags='+faststart' # ускоренный старт для веба
        ).global_args('-shortest')  # Останавливаем по более короткой дорожке (аудио или видео)

        try:
            ffmpeg.run(output_stream, capture_stderr=True, quiet=False)
        except ffmpeg.Error as e:
            print("Ошибка при создании видео:")
            print(e.stderr.decode('utf8'))
            raise

        # Читаем результат и возвращаем
        with open(tmp_video_name, "rb") as f:
            video_bytes = f.read()

        return video_bytes

    finally:
        # Чистим временные файлы
        for f in [tmp_audio_name, tmp_audio_converted_name, tmp_image_name, tmp_video_name]:
            try:
                os.remove(f)
            except OSError:
                pass


# def test_crop():
#    filename = "./examples/fire.png"
#    buffer = None
#    with open(filename, "rb") as f:
#        buffer = f.read()
#    print(len(buffer))
#    new_buffer = crop_to_square(io.BytesIO(buffer))
#    with open("./examples/new_fire.png", "wb") as f:
#        f.write(new_buffer.getbuffer())
#    print('ok')
#
#if __name__ == "__main__":
#    test_crop()
