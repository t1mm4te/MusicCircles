from dotenv import load_dotenv  # type: ignore
import os


# Загрузка переменных окружения
load_dotenv()

TB_TOKEN = os.getenv('TB_TOKEN')
if not TB_TOKEN:
    raise ValueError('Необходимо установить переменную окружения '
                     'TB_TOKEN (Telegram Bot Token)')

DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER')
if not DOWNLOAD_FOLDER:
    raise ValueError('Необходимо установить переменную окружения '
                     'DOWNLOAD_FOLDER (папка для загрузки файлов)')

AUDIO_RECEIVER_API_URL = os.getenv('AUDIO_RECEIVER_API_URL')
if not AUDIO_RECEIVER_API_URL:
    raise ValueError('Необходимо установить переменную окружения '
                     'AUDIO_RECEIVER_API_URL (URL для доступа к API)')

MEDIA_PROCESSOR_API_URL = os.getenv('MEDIA_PROCESSOR_API_URL')
if not MEDIA_PROCESSOR_API_URL:
    raise ValueError('Необходимо установить переменную окружения '
                     'MEDIA_PROCESSOR_API_URL (URL для доступа к API)')

DATABASE_API_URL = os.getenv('DATABASE_API_URL')
if not DATABASE_API_URL:
    raise ValueError('Необходимо установить переменную окружения '
                     'DATABASE_API_URL (URL для доступа к API)')
