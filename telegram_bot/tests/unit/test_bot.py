import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
import io
from telegram import Update, Message, User, Chat, Audio, CallbackQuery
from telegram.ext import ContextTypes

import src.handlers as handlers
import src.states as st
import src.config as conf


@pytest.fixture
def mock_context():
    """Создает мок контекста с user_data."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.bot = AsyncMock()
    return context


@pytest.fixture
def mock_user():
    """Создает мок пользователя."""
    return User(
        id=12345,
        is_bot=False,
        first_name="Test",
        username="testuser"
    )


@pytest.fixture
def mock_chat():
    """Создает мок чата."""
    return Chat(
        id=67890,
        type="private"
    )


@pytest.fixture
def mock_audio_message(mock_user, mock_chat):
    """Создает мок сообщения с аудио."""
    audio = Audio(
        file_id="test_audio_file_id",
        file_unique_id="unique_id",
        duration=180,
        mime_type="audio/mpeg",
        file_size=5000000
    )

    message = MagicMock(spec=Message)
    message.from_user = mock_user
    message.chat = mock_chat
    message.audio = audio
    message.voice = None
    message.reply_text = AsyncMock()

    return message


@pytest.fixture
def mock_text_message(mock_user, mock_chat):
    """Создает мок текстового сообщения."""
    message = MagicMock(spec=Message)
    message.from_user = mock_user
    message.chat = mock_chat
    message.text = "Test Song Name"
    message.reply_text = AsyncMock()

    return message


@pytest.fixture
def mock_update_with_message(mock_audio_message):
    """Создает мок обновления с сообщением."""
    update = MagicMock(spec=Update)
    update.message = mock_audio_message
    update.callback_query = None
    update.effective_chat = mock_audio_message.chat
    return update


@pytest.fixture
def mock_update_with_text(mock_text_message):
    """Создает мок обновления с текстовым сообщением."""
    update = MagicMock(spec=Update)
    update.message = mock_text_message
    update.callback_query = None
    update.effective_chat = mock_text_message.chat
    return update


@pytest.fixture
def mock_callback_query(mock_user, mock_chat):
    """Создает мок callback query."""
    query = MagicMock(spec=CallbackQuery)
    query.from_user = mock_user
    query.data = "test_callback_data"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    # Создаем мок сообщения для callback query
    message = MagicMock(spec=Message)
    message.chat = mock_chat
    query.message = message

    return query


@pytest.fixture
def mock_update_with_callback(mock_callback_query):
    """Создает мок обновления с callback query."""
    update = MagicMock(spec=Update)
    update.callback_query = mock_callback_query
    update.message = None
    update.effective_chat = mock_callback_query.message.chat
    return update


class TestBotIntegration:

    @pytest.mark.asyncio
    async def test_start_command_flow(self, mock_update_with_text, mock_context):
        """Тест команды /start."""
        update = mock_update_with_text
        context = mock_context

        result = await handlers.start(update, context)

        assert result is None
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Привет, я бот" in call_args
        assert context.user_data == {}

    @pytest.mark.asyncio
    @patch('src.api_utils.search_for_tracks')
    async def test_search_audio_by_name_success(self, mock_search, mock_update_with_text, mock_context):
        """Тест успешного поиска песни по названию."""
        from src.api_utils import TrackInfo
        mock_tracks = [
            TrackInfo(id=1, title="Test Song",
                      artists="Test Artist", duration=180),
            TrackInfo(id=2, title="Another Song",
                      artists="Another Artist", duration=200)
        ]
        mock_search.return_value = mock_tracks

        update = mock_update_with_text
        context = mock_context

        result = await handlers.search_audio_by_name(update, context)

        assert result == st.SELECTING_SONG
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "Выбери одну песню" in call_args[0][0]
        assert call_args[1]['reply_markup'] is not None

    @pytest.mark.asyncio
    @patch('src.api_utils.search_for_tracks')
    async def test_search_audio_by_name_no_results(self, mock_search, mock_update_with_text, mock_context):
        """Тест поиска песни без результатов."""
        mock_search.return_value = []

        update = mock_update_with_text
        context = mock_context

        result = await handlers.search_audio_by_name(update, context)

        assert result is None
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Ничего не получилось найти" in call_args

    @pytest.mark.asyncio
    @patch('src.api_utils.search_for_tracks')
    async def test_search_audio_by_name_api_error(self, mock_search, mock_update_with_text, mock_context):
        """Тест ошибки API при поиске песни."""
        mock_search.return_value = None

        update = mock_update_with_text
        context = mock_context

        result = await handlers.search_audio_by_name(update, context)

        assert result is None
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Произошла ошибка" in call_args

    @pytest.mark.asyncio
    @patch('src.api_utils.get_track_info')
    async def test_save_selected_audio_success(self, mock_get_info, mock_update_with_callback, mock_context):
        """Тест успешного сохранения выбранной песни."""
        mock_get_info.return_value = 180  # duration in seconds

        update = mock_update_with_callback
        update.callback_query.data = "123"
        context = mock_context

        result = await handlers.save_selected_audio(update, context)

        from telegram.ext import ConversationHandler
        assert result == ConversationHandler.END
        assert context.user_data[st.TRACK_ID] == "123"
        assert context.user_data[st.FILE_DURATION] == "180"
        assert context.user_data[st.DURATION_LEFT_BORDER] == "0"
        assert context.user_data[st.DURATION_RIGHT_BORDER] == "60"

        update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    @patch('src.api_utils.get_track_info')
    async def test_save_selected_audio_api_error(self, mock_get_info, mock_update_with_callback, mock_context):
        """Тест ошибки API при получении информации о треке."""
        mock_get_info.return_value = None

        update = mock_update_with_callback
        update.callback_query.data = "123"
        context = mock_context

        result = await handlers.save_selected_audio(update, context)

        assert result == st.TYPING_SONG_NAME
        update.callback_query.edit_message_text.assert_called_once()
        call_args = update.callback_query.edit_message_text.call_args[0][0]
        assert "Произошла ошибка" in call_args

    @pytest.mark.asyncio
    async def test_print_time_codes(self, mock_update_with_callback, mock_context):
        """Тест показа меню установки времени."""

        update = mock_update_with_callback
        context = mock_context
        context.user_data[st.FILE_DURATION] = "120"

        result = await handlers.print_time_codes(update, context)

        assert result == st.SELECTING_ACTION
        update.callback_query.edit_message_text.assert_called_once()
        call_args = update.callback_query.edit_message_text.call_args
        assert "давай обрежем" in call_args[0][0]
        assert call_args[1]['reply_markup'] is not None

    @pytest.mark.asyncio
    async def test_set_start_time(self, mock_update_with_callback, mock_context):
        """Тест установки времени с начала."""

        update = mock_update_with_callback
        context = mock_context
        context.user_data[st.FILE_DURATION] = "120"

        result = await handlers.set_start_time(update, context)

        from telegram.ext import ConversationHandler
        assert result == ConversationHandler.END
        assert context.user_data[st.DURATION_LEFT_BORDER] == "0"
        assert context.user_data[st.DURATION_RIGHT_BORDER] == "60"

        update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_custom_time_single_value(self, mock_update_with_text, mock_context):
        """Тест установки пользовательского времени (одно значение)."""

        update = mock_update_with_text
        update.message.text = "30"
        context = mock_context
        context.user_data[st.FILE_DURATION] = "120"

        result = await handlers.set_custom_time(update, context)

        from telegram.ext import ConversationHandler
        assert result == ConversationHandler.END
        assert context.user_data[st.DURATION_LEFT_BORDER] == "30"
        assert context.user_data[st.DURATION_RIGHT_BORDER] == "90"

        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_custom_time_two_values(self, mock_update_with_text, mock_context):
        """Тест установки пользовательского времени (два значения)."""

        update = mock_update_with_text
        update.message.text = "30 90"
        context = mock_context
        context.user_data[st.FILE_DURATION] = "120"

        result = await handlers.set_custom_time(update, context)

        from telegram.ext import ConversationHandler
        assert result == ConversationHandler.END
        assert context.user_data[st.DURATION_LEFT_BORDER] == "30"
        assert context.user_data[st.DURATION_RIGHT_BORDER] == "90"

        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_custom_time_mm_ss_format(self, mock_update_with_text, mock_context):
        """Тест установки времени в формате мм:сс."""

        update = mock_update_with_text
        update.message.text = "1:30 2:00"
        context = mock_context
        context.user_data[st.FILE_DURATION] = "180"

        result = await handlers.set_custom_time(update, context)

        from telegram.ext import ConversationHandler
        assert result == ConversationHandler.END
        assert context.user_data[st.DURATION_LEFT_BORDER] == "90"
        assert context.user_data[st.DURATION_RIGHT_BORDER] == "120"

        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_back_to_menu(self, mock_update_with_callback, mock_context):
        """Тест возврата в главное меню."""

        update = mock_update_with_callback
        context = mock_context
        context.user_data[st.DURATION_LEFT_BORDER] = "0"
        context.user_data[st.DURATION_RIGHT_BORDER] = "60"

        result = await handlers.back_to_menu(update, context)

        from telegram.ext import ConversationHandler
        assert result == ConversationHandler.END
        update.callback_query.edit_message_text.assert_called_once()
        call_args = update.callback_query.edit_message_text.call_args
        assert "Выберите опцию" in call_args[0][0]
        assert call_args[1]['reply_markup'] is not None

    @pytest.mark.asyncio
    async def test_restart_conversation_from_message(self, mock_update_with_text, mock_context):
        """Тест перезапуска разговора из сообщения."""

        update = mock_update_with_text
        context = mock_context
        context.user_data['some_data'] = 'test'

        result = await handlers.restart_conversation(update, context)

        assert result == st.TYPING_SONG_NAME
        assert context.user_data == {}
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Введите название песни" in call_args

    @pytest.mark.asyncio
    async def test_restart_conversation_from_callback(self, mock_update_with_callback, mock_context):
        """Тест перезапуска разговора из callback query."""

        update = mock_update_with_callback
        context = mock_context
        context.user_data['some_data'] = 'test'

        result = await handlers.restart_conversation(update, context)

        assert result == st.TYPING_SONG_NAME
        assert context.user_data == {}
        update.callback_query.edit_message_text.assert_called_once()
        call_args = update.callback_query.edit_message_text.call_args[0][0]
        assert "Введите название песни" in call_args

    @pytest.mark.asyncio
    async def test_get_main_menu(self, mock_context):
        """Тест генерации главного меню."""

        context = mock_context
        context.user_data[st.DURATION_LEFT_BORDER] = "10"
        context.user_data[st.DURATION_RIGHT_BORDER] = "70"

        keyboard = handlers.get_main_menu(context)

        assert keyboard is not None
        inline_keyboard = keyboard.inline_keyboard
        assert len(inline_keyboard) == 3

        first_button_text = inline_keyboard[0][0].text
        assert "с 10с по 70с" in first_button_text

        assert inline_keyboard[0][0].callback_data == st.SET_TIME_CODE
        assert inline_keyboard[1][0].callback_data == st.CREATE_VIDEO_MESSAGE
        assert inline_keyboard[2][0].callback_data == str(st.RESTART_SEARCH)

    def test_get_seconds_mm_ss_format(self):
        """Тест парсинга времени в формате мм:сс."""
        assert handlers.get_seconds("1:30") == 90
        assert handlers.get_seconds("0:45") == 45
        assert handlers.get_seconds("2:15") == 135

    def test_get_seconds_ss_format(self):
        """Тест парсинга времени в формате сс."""
        assert handlers.get_seconds("30") == 30
        assert handlers.get_seconds("120") == 120
        assert handlers.get_seconds("0") == 0

    def test_get_file_name_extension(self):
        """Тест получения расширения файла по MIME-типу."""
        assert handlers.get_file_name_extension("audio/mpeg") == ".mp3"
        assert handlers.get_file_name_extension("audio/ogg") == ".ogg"
        assert handlers.get_file_name_extension("audio/x-wav") == ".wav"
        assert handlers.get_file_name_extension("unknown/type") == ""

    @pytest.mark.asyncio
    async def test_clear_user_data_with_file(self, mock_update_with_text, mock_context):
        """Тест очистки данных пользователя с удалением файла."""

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name

        update = mock_update_with_text
        context = mock_context
        context.user_data[st.TRACK_FILE_PATH] = temp_file_path
        context.user_data['other_data'] = 'test'

        handlers.clear_user_data(update, context)

        assert context.user_data == {}
        assert not os.path.exists(temp_file_path)

    @pytest.mark.asyncio
    async def test_clear_user_data_file_not_exists(self, mock_update_with_text, mock_context):
        """Тест очистки данных пользователя когда файл не существует."""

        update = mock_update_with_text
        context = mock_context
        context.user_data[st.TRACK_FILE_PATH] = "/nonexistent/file.mp3"
        context.user_data['other_data'] = 'test'

        handlers.clear_user_data(update, context)

        assert context.user_data == {}

    @pytest.mark.asyncio
    async def test_clear_user_data_from_callback(self, mock_update_with_callback, mock_context):
        """Тест очистки данных пользователя из callback query."""

        update = mock_update_with_callback
        context = mock_context
        context.user_data['test_data'] = 'test'

        handlers.clear_user_data(update, context)

        assert context.user_data == {}


class TestCreateVideoIntegration:
    """Интеграционные тесты для создания видео."""

    @pytest.mark.asyncio
    @patch('src.api_utils.download_track_stream')
    @patch('src.api_utils.trim_audio')
    @patch('src.api_utils.download_cover')
    @patch('src.api_utils.create_video')
    @patch('builtins.open')
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('os.remove')
    @patch('os.makedirs')
    async def test_create_video_message_success(
        self,
        mock_makedirs,
        mock_remove,
        mock_listdir,
        mock_exists,
        mock_open,
        mock_create_video,
        mock_download_cover,
        mock_trim_audio,
        mock_download_stream,
        mock_update_with_callback,
        mock_context
    ):
        """Тест успешного создания видео-кружка."""

        mock_download_stream.return_value = "/tmp/test_track.mp3"
        mock_trim_audio.return_value = True
        mock_download_cover.return_value = "/tmp/test_cover.jpg"
        mock_create_video.return_value = True
        mock_exists.return_value = True
        mock_listdir.return_value = ["video_test_track.mp4"]

        mock_file_content = b"fake_video_content"
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = mock_file_content
        mock_open.return_value = mock_file

        update = mock_update_with_callback
        context = mock_context
        context.user_data[st.TRACK_ID] = "test_track"
        context.user_data[st.DURATION_LEFT_BORDER] = "10"
        context.user_data[st.DURATION_RIGHT_BORDER] = "70"

        result = await handlers.create_video_message(update, context)

        from telegram.ext import ConversationHandler
        assert result == ConversationHandler.END

        mock_download_stream.assert_called_once_with(
            track_id="test_track",
            save_dir=conf.DOWNLOAD_FOLDER
        )
        mock_trim_audio.assert_called_once()
        mock_download_cover.assert_called_once_with(
            track_id="test_track",
            save_dir=conf.DOWNLOAD_FOLDER
        )
        mock_create_video.assert_called_once()

        context.bot.send_video_note.assert_called_once()

    @pytest.mark.asyncio
    @patch('src.api_utils.download_track_stream')
    @patch('src.api_utils.trim_audio')
    @patch('os.remove')
    async def test_create_video_message_trim_error(
        self,
        mock_remove,
        mock_trim_audio,
        mock_download_stream,
        mock_update_with_callback,
        mock_context
    ):
        """Тест ошибки при обрезке аудио."""

        mock_download_stream.return_value = "/tmp/test_track.mp3"
        mock_trim_audio.return_value = False

        update = mock_update_with_callback
        context = mock_context
        context.user_data[st.TRACK_ID] = "test_track"
        context.user_data[st.DURATION_LEFT_BORDER] = "10"
        context.user_data[st.DURATION_RIGHT_BORDER] = "70"

        result = await handlers.create_video_message(update, context)

        from telegram.ext import ConversationHandler
        assert result == ConversationHandler.END

        update.callback_query.edit_message_text.assert_called()
        call_args = update.callback_query.edit_message_text.call_args
        assert call_args is not None
        if call_args[0]:
            assert "Ошибка, при создании кружка" in call_args[0][0]
        elif call_args[1].get('text'):
            assert "Ошибка, при создании кружка" in call_args[1]['text']

    @pytest.mark.asyncio
    @patch('src.api_utils.download_track_stream')
    @patch('src.api_utils.trim_audio')
    @patch('src.api_utils.download_cover')
    @patch('src.api_utils.create_video')
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('os.remove')
    async def test_create_video_message_video_not_found(
        self,
        mock_remove,
        mock_listdir,
        mock_exists,
        mock_create_video,
        mock_download_cover,
        mock_trim_audio,
        mock_download_stream,
        mock_update_with_callback,
        mock_context
    ):
        """Тест случая, когда видеофайл не найден."""

        mock_download_stream.return_value = "/tmp/test_track.mp3"
        mock_trim_audio.return_value = True
        mock_download_cover.return_value = "/tmp/test_cover.jpg"
        mock_create_video.return_value = True
        mock_exists.return_value = False
        mock_listdir.return_value = []

        update = mock_update_with_callback
        context = mock_context
        context.user_data[st.TRACK_ID] = "test_track"
        context.user_data[st.DURATION_LEFT_BORDER] = "10"
        context.user_data[st.DURATION_RIGHT_BORDER] = "70"

        result = await handlers.create_video_message(update, context)

        from telegram.ext import ConversationHandler
        assert result == ConversationHandler.END

        update.callback_query.edit_message_text.assert_called()
        call_args = update.callback_query.edit_message_text.call_args
        assert call_args is not None
        if call_args[0]:
            assert "Ошибка, при создании кружка" in call_args[0][0]
        elif call_args[1].get('text'):
            assert "Ошибка, при создании кружка" in call_args[1]['text']
