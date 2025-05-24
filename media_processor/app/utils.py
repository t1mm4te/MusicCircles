import io
from fastapi import UploadFile, HTTPException
from PIL import Image
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

async def validate_image_content(file: UploadFile):
    """
    Проверка изображения на корректность формата

    Args:
        file: Загружаемый файл с изображением.
    """
    content = await file.read()
    try:
        Image.open(io.BytesIO(content))
    except Exception:
        raise HTTPException(400, "Не удалось обработать файл как изображение")
    return content

async def validate_audio_content(file: UploadFile) -> bytes:
    """
    Проверка аудио на корректность формата

    Args:
        file: Загружаемый аудиофайл.
    """
    content = await file.read()
    try:
        AudioSegment.from_file(io.BytesIO(content))
    except CouldntDecodeError:
        raise HTTPException(400, "Файл не является поддерживаемым аудиоформатом")
    except Exception:
        raise HTTPException(400, "Не удалось обработать аудиофайл")
    return content

def validate_audio_range(start: int, end: int):
    """
    Проверка логической корректности диапазона.

    Args:
        start: Начало обрезки.
        end: Конец обрезки.
    """
    if start < 0 or end < 0:
        raise HTTPException(status_code=400, detail="Параметры времени не могут быть отрицательными")
    if start >= end:
        raise HTTPException(status_code=400, detail="Параметр start должен быть меньше end")

def validate_audio_duration(contents: bytes, start: int, end: int):
    """
    Проверка, что start и end не превышают длительность аудио.

    Args:
        contents: Аудиофайл в байтах
        start: Начало обрезки.
        end: Конец обрезки.
    """
    try:
        audio = AudioSegment.from_file(io.BytesIO(contents))
        duration = audio.duration_seconds
    except Exception:
        raise HTTPException(status_code=400, detail="Не удалось определить длительность аудио")

    if start > duration or end > duration:
        raise HTTPException(
            status_code=400,
            detail=f"Параметры start и end не должны превышать длительность аудио ({duration:.2f} сек)"
        )