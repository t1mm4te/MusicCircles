import os
import logging
import httpx
from typing import NamedTuple


logger = logging.getLogger(__name__)


class Response(NamedTuple):
    data: dict
    had_error: bool


async def get_data_from_api(
        url: str,
        params: dict[str, str] | None = None
        ) -> Response:
    had_error = False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()  # Проверяем на ошибки HTTP (4xx, 5xx)

    except httpx.HTTPStatusError as e:
        logger.error(
            'Ошибка HTTP при запросе к FastAPI: '
            f'{e.response.status_code} - {e.response.text}'
        )
        had_error = True

    except httpx.RequestError as e:
        logger.error(f'Ошибка соединения с FastAPI: {e}')
        had_error = True

    except Exception as e:
        logger.error(f'Непредвиденная ошибка: {e}')
        had_error = True

    if had_error:
        return Response(data={}, had_error=had_error)

    data = response.json()

    return Response(data=data, had_error=had_error)


async def download_track_stream(
    url: str,
    song_id: str,
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
            file_path = os.path.join(save_dir, f'{song_id}{ext}')

            # Записываем чанки по мере поступления
            with open(file_path, "wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)

    return file_path
