import logging
import httpx
from typing import Optional

import src.config as conf


logger = logging.getLogger(__name__)


async def log_interaction(
    user_id: int,
    username: Optional[str],
    interaction_type: str
) -> bool:
    """
    Логирует взаимодействие пользователя в базе данных.

    Args:
        user_id: ID пользователя Telegram
        username: Username пользователя (может быть None)
        interaction_type: Тип взаимодействия ("Поиск песни" или "Создание видео")

    Returns:
        bool: True если успешно, False если произошла ошибка
    """
    url = f'{conf.DATABASE_API_URL}/log-interaction/'

    payload = {
        "user_id": user_id,
        "username": username,
        "interaction_type": interaction_type
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(
                f"Logged interaction: {interaction_type} for user {user_id}")
            return True

    except httpx.HTTPStatusError as e:
        logger.error(
            f'HTTP error when logging interaction: '
            f'{e.response.status_code} - {e.response.text}'
        )
        return False

    except httpx.RequestError as e:
        logger.error(f'Connection error when logging interaction: {e}')
        return False

    except Exception as e:
        logger.error(f'Unexpected error when logging interaction: {e}')
        return False
