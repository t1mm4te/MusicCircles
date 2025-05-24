from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from urllib.parse import quote_plus
import io
import os

from .schemas import HTTPError
from .services import trim_audio, create_video_from_audio_and_cover_files
from .utils import validate_audio_content, validate_image_content, validate_audio_range, validate_audio_duration

router = APIRouter()

@router.post(
    "/trim_audio",
    response_model=None,
    responses={
        400: {
            "model": HTTPError,
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Параметр start должен быть меньше end"
                    }
                }
            }
        }
    }
)
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

    # Проверка корректности параметров start и end
    validate_audio_range(start, end)
    # Проверка, что это действительно поддерживаемый аудиофайл
    contents = await validate_audio_content(file)
    # Проверка длительности файла в секундах
    validate_audio_duration(contents, start, end)

    trimmed_audio_buffer = await trim_audio(contents, start, end)
    filename_base, ext = os.path.splitext(file.filename)
    output_filename = f"cut_{filename_base}_{start}_{end}.mp3"
    encoded_filename = quote_plus(output_filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
    }
    return StreamingResponse(trimmed_audio_buffer, media_type="audio/mpeg", headers=headers)



@router.post(
    "/create_video",
    response_model=None,
    responses={
        400: {
            "model": HTTPError,
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Параметр start должен быть меньше end"
                    }
                }
            }
        }
    }
)
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
    audio_content = await validate_audio_content(audio_file)
    image_content = await validate_image_content(image_file)

    video_bytes = create_video_from_audio_and_cover_files(io.BytesIO(audio_content), io.BytesIO(image_content))
    filename_base_audio, _ = os.path.splitext(audio_file.filename)
    filename_base_image, _ = os.path.splitext(image_file.filename)
    output_filename = f"{filename_base_audio}_with_cover_{filename_base_image}.mp4"
    encoded_filename = quote_plus(output_filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
    }
    return StreamingResponse(io.BytesIO(video_bytes), media_type="video/mp4", headers=headers)
