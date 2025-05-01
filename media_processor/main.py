from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from pydub import AudioSegment
import io
import os
from urllib.parse import quote_plus
import ffmpeg
import tempfile
from typing import BinaryIO
import uuid

app = FastAPI()

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

def create_video_from_audio_and_cover_files(audio_file: BinaryIO, image_file: BinaryIO) -> bytes:
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

        with open(tmp_image_name, "wb") as f:
            f.write(image_file.read())

        # Перекодируем аудио в AAC-LC
        audio_stream = ffmpeg.input(tmp_audio_name)
        audio_stream = ffmpeg.output(
            audio_stream,
            tmp_audio_converted_name,
            acodec='aac',
            ar='44100',
            ac='2'
        )
        try:
            ffmpeg.run(audio_stream, capture_stderr=True, quiet=False)
        except ffmpeg.Error as e:
            print("Ошибка при перекодировании аудио:")
            print(e.stderr.decode('utf8'))
            raise

        # Создаём видео из изображения и перекодированного аудио
        image_stream = ffmpeg.input(tmp_image_name, loop=1, framerate=25)
        # Добавляем фильтр scale для изменения размера изображения на четные значения
        scaled_image_stream = image_stream.filter('scale', 'ceil(iw/2)*2', 'ceil(ih/2)*2')
        video_stream = ffmpeg.input(tmp_audio_converted_name)
        output_stream = ffmpeg.output(
            scaled_image_stream,
            video_stream,
            tmp_video_name,
            vcodec='libx264',
            acodec='aac',
            pix_fmt='yuv420p',
            shortest=None
        )
        try:
            ffmpeg.run(output_stream, capture_stderr=True, quiet=False)
        except ffmpeg.Error as e:
            print("Ошибка при создании видео:")
            print(e.stderr.decode('utf8'))
            raise

        # Возвращаем видео как байты
        with open(tmp_video_name, "rb") as f:
            video_bytes = f.read()

        return video_bytes

    finally:
        # Удаляем временные файлы
        for f in [tmp_audio_name, tmp_audio_converted_name, tmp_image_name, tmp_video_name]:
            try:
                os.remove(f)
            except OSError:
                pass

@app.post("/trim_audio")
async def trim_audio_endpoint(file: UploadFile = File(...), start: int = Form(...), end: int = Form(...)):
    """
    Endpoint для обрезки аудиофайла.

    Args:
        file: Загружаемый аудиофайл.
        start: Начало отрезка в секундах (передается как Form-параметр).
        end: Конец отрезка в секундах (передается как Form-параметр).

    Returns:
        StreamingResponse: HTTP-ответ с обрезанным аудиофайлом.
    """
    contents = await file.read()
    trimmed_audio_buffer = await trim_audio(contents, start, end)
    filename_base, ext = os.path.splitext(file.filename)
    output_filename = f"cut_{filename_base}_{start}_{end}.mp3"
    encoded_filename = quote_plus(output_filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
    }
    return StreamingResponse(trimmed_audio_buffer, media_type="audio/mpeg", headers=headers)

@app.post("/create_video")
async def create_video_endpoint(
    audio_file: UploadFile = File(...),
    image_file: UploadFile = File(...)
):
    """
    Endpoint для создания видео из аудио и обложки.

    Args:
        audio_file: Загружаемый аудиофайл.
        image_file: Загружаемый файл с изображением (обложка).

    Returns:
        StreamingResponse: HTTP-ответ с созданным видеофайлом.
    """
    audio_content = await audio_file.read()
    image_content = await image_file.read()
    video_bytes = create_video_from_audio_and_cover_files(io.BytesIO(audio_content), io.BytesIO(image_content))
    filename_base_audio, _ = os.path.splitext(audio_file.filename)
    filename_base_image, _ = os.path.splitext(image_file.filename)
    output_filename = f"{filename_base_audio}_with_cover_{filename_base_image}.mp4"
    encoded_filename = quote_plus(output_filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
    }
    return StreamingResponse(io.BytesIO(video_bytes), media_type="video/mp4", headers=headers)

# Инструкции по запуску FastAPI (для локального тестирования):
# 1. Установите необходимые библиотеки: pip install fastapi uvicorn pydub ffmpeg-python
# 2. Сохраните этот код в файл, например, main.py
# 3. Убедитесь, что ffmpeg установлен и добавлен в системный PATH.
# 4. Запустите сервер FastAPI: uvicorn main:app --reload

# Для тестирования этого endpoint вы можете использовать такие инструменты, как curl или Postman.
# Например, с помощью curl:
# curl -X POST -F "audio_file=@/путь/к/аудиофайлу.mp3" -F "image_file=@/путь/к/изображению.png" http://127.0.0.1:8000/create_video --output output.mp4