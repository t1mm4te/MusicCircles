import pytest
import os
import tempfile


# Устанавливаем разумные значения по умолчанию для локальных запусков,
# но не перезаписываем значения, уже переданные через container/.env.
os.environ.setdefault('TB_TOKEN', 'test_token')
os.environ.setdefault('DOWNLOAD_FOLDER', '/tmp/test_downloads')
os.environ.setdefault('AUDIO_RECEIVER_API_URL', 'http://audio_receiver:9000')
os.environ.setdefault('MEDIA_PROCESSOR_API_URL', 'http://media_processor:8000')
os.environ.setdefault('DATABASE_API_URL', 'http://database:8001')


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Настройка тестового окружения."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Принудительно изолируем только DOWNLOAD_FOLDER для артефактов тестов.
        os.environ['DOWNLOAD_FOLDER'] = temp_dir
        yield


@pytest.fixture
def temp_download_folder():
    """Создает временную папку для загрузок."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir
