from dotenv import load_dotenv  # type: ignore
import os


# Загрузка переменных окружения
load_dotenv()

TB_TOKEN = os.getenv('TB_TOKEN')
if not TB_TOKEN:
    raise ValueError('Необходимо установить переменную окружения '
                     'TB_TOKEN (Telegram Bot Token)')

DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER')
if not TB_TOKEN:
    raise ValueError('Необходимо установить переменную окружения '
                     'DOWNLOAD_FOLDER (папка для загрузки файлов)')
