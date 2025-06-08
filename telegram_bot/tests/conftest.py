import pytest
import os
import tempfile
from unittest.mock import patch


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Настройка тестового окружения."""
    # Устанавливаем переменные окружения для тестов
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ['DOWNLOAD_FOLDER'] = temp_dir
        os.environ['TB_TOKEN'] = 'test_token'
        os.environ['AUDIO_RECEIVER_API_URL'] = 'http://test-audio-api'
        os.environ['MEDIA_PROCESSOR_API_URL'] = 'http://test-media-api'
        yield


@pytest.fixture
def temp_download_folder():
    """Создает временную папку для загрузок."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture(autouse=True)
def mock_config():
    """Мокает конфигурацию для тестов."""
    with patch('src.config.DOWNLOAD_FOLDER', '/tmp/test_downloads'):
        yield