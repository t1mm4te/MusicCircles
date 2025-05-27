import os
import logging
import httpx
from typing import NamedTuple
import traceback

import src.config as conf


logger = logging.getLogger(__name__)


class Response(NamedTuple):
    data: dict
    had_error: bool


class TrackInfo(NamedTuple):
    id: int
    title: str
    artists: str
    duration: int


async def search_for_tracks(
    track_name: str
) -> list[TrackInfo] | None:
    """
    Поиск треков по названию.
    Возвращает список треков (возможно пустой).
    """

    url = f'{conf.AUDIO_RECEIVER_API_URL}/search/'
    params = {'query': track_name}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()

    except httpx.HTTPStatusError as e:
        logger.error(
            'Ошибка HTTP при запросе к API: '
            f'{e.response.status_code} - {e.response.text}'
        )
        return None

    except httpx.RequestError as e:
        logger.error(f'Ошибка соединения с API: {e}')
        return None

    except Exception as e:
        logger.error(f'Непредвиденная ошибка: {e}')
        return None

    data = response.json().get('results', [])

    tracks: list[TrackInfo] = []

    for track in data:
        id = track.get('id')
        title = track.get('title', 'Без названия')
        artists = ', '.join(track.get('artists', ['Неизвестный']))
        duration = track.get('duration') // 1000  # In seconds.

        tracks.append(
            TrackInfo(
                id=id,
                title=title,
                artists=artists,
                duration=duration
            )
        )

    return tracks


async def get_track_info(
    track_id: str
) -> int | None:
    """Получение информации о треке по id."""

    url = f'{conf.AUDIO_RECEIVER_API_URL}/track/{track_id}/info'
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()

    except httpx.HTTPStatusError as e:
        logger.error(
            'Ошибка HTTP при запросе к FastAPI: '
            f'{e.response.status_code} - {e.response.text}'
        )
        return None

    except httpx.RequestError as e:
        logger.error(f'Ошибка соединения с FastAPI: {e}')
        return None

    except Exception as e:
        logger.error(f'Непредвиденная ошибка: {e}')
        return None

    duration = response.json().get('duration')

    if not isinstance(duration, int):
        logger.error(f'duration не int: {duration.__class__}')
        return None

    return duration // 1000  # Duration in seconds.


async def download_track_stream(
    url: str,
    track_id: str,
    save_dir: str
) -> str:
    """
    Скачивает весь MP3 по треку track_id (стриминг)
    и сохраняет в папку save_dir.
    Возвращает путь к сохранённому файлу.
    """

    async with httpx.AsyncClient() as client:
        # Используем streaming, чтобы не держать в памяти весь файл
        async with client.stream("GET", url, timeout=30.0) as resp:
            resp.raise_for_status()

            ext = '.mp3'

            os.makedirs(save_dir, exist_ok=True)
            file_path = os.path.join(save_dir, f'{track_id}{ext}')

            # Записываем чанки по мере поступления
            with open(file_path, "wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)

    return file_path


async def download_cover(
    url: str,
    song_id: str,
    save_dir: str
) -> str:
    """
    Скачивает обложку трека track_id и сохраняет в папку save_dir.
    Возвращает путь к сохранённому файлу.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()

        ext = '.jpg'

        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, f'{song_id}{ext}')

        with open(file_path, "wb") as f:
            f.write(response.content)

    return file_path


async def trim_audio(
        url: str,
        file_path: str,
        start: int,
        end: int,
        output_path: str
) -> bool:
    """
    Обрезает аудиофайл через API и сохраняет его по указанному пути.

    Args:
        file_path (str): Путь к исходному аудиофайлу.
        start (int): Время начала обрезки в секундах.
        end (int): Время окончания обрезки в секундах.
        output_path (str): Путь для сохранения обрезанного файла.

    Returns:
        bool: True, если успешно, иначе False.
    """

    try:
        with open(file_path, 'rb') as file:
            files = {'file': file}
            data = {'start': str(start), 'end': str(end)}

            async with httpx.AsyncClient() as client:
                response = await client.post(url, files=files, data=data)
                response.raise_for_status()

                with open(output_path, 'wb') as output_file:
                    output_file.write(response.content)

        return True

    except Exception as e:
        logger.error(f"Ошибка при обращении к API для обрезки аудио: {e}")
        return False


async def create_video(
        url: str,
        audio_path: str,
        image_path: str,
        output_path: str
) -> bool:
    """
    Создает видео из аудиофайла и изображения через API и сохраняет его по указанному пути.

    Args:
        audio_path (str): Путь к исходному аудиофайлу.
        image_path (str): Путь к изображению (обложка).
        output_path (str): Путь для сохранения созданного видео.

    Returns:
        bool: True, если успешно, иначе False.
    """

    timeout_seconds = 120.0
    timeout_config = httpx.Timeout(timeout_seconds, connect=10.0)

    try:
        with open(audio_path, 'rb') as audio_file, open(image_path, 'rb') as image_file:
            logger.info('[create_video] Начинаю отправлять данные.')
            files = {
                'audio_file': audio_file,
                'image_file': image_file
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    files=files,
                    timeout=timeout_config
                )
                response.raise_for_status()

                with open(output_path, 'wb') as output_file:
                    output_file.write(response.content)

        return True

    except Exception as e:
        logger.error(
            f"[{type(e).__name__}] Ошибка при обращении к API: {repr(e)}")
        logger.error(traceback.format_exc())
        return False
