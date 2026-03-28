import os
import pytest
import httpx
from unittest.mock import patch, AsyncMock, MagicMock
from telegram.ext import ConversationHandler
import tempfile

import src.states as st
import src.config as conf
from src.api_utils import TrackInfo
from src.handlers import (
    search_audio_by_name,
    save_selected_audio,
    set_custom_time,
    create_video_message,
    restart_conversation
)


def get_mock_update_message(text="test query"):
    update = MagicMock()
    update.message = AsyncMock()
    update.message.text = text
    update.message.from_user.id = 123
    update.message.from_user.username = "test_user"
    update.message.reply_text = AsyncMock()
    return update


def get_mock_update_callback_query(data="1"):
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.data = data
    update.callback_query.from_user.id = 123
    update.callback_query.from_user.username = "test_user"
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = 456
    return update


def get_mock_context():
    context = MagicMock()
    context.user_data = {}
    context.bot = AsyncMock()
    return context


@pytest.mark.asyncio
async def test_scenario_1_successful_search_audio():
    """Сценарий 1. Успешный поиск аудиозаписи. Бот выдает варианты."""
    update = get_mock_update_message("Oasis Wonderwall")
    context = get_mock_context()

    mock_db_response = MagicMock()
    mock_db_response.raise_for_status = MagicMock()

    mock_search_response = MagicMock()
    mock_search_response.json.return_value = {
        "results": [
            {"id": "1", "title": "Wonderwall", "artists": [
                "Oasis"], "duration": 258000, "url": "http://test"}
        ]
    }
    mock_search_response.raise_for_status = MagicMock()

    with patch("src.database_utils.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
            patch("src.api_utils.httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:

        mock_post.return_value = mock_db_response
        mock_get.return_value = mock_search_response

        result = await search_audio_by_name(update, context)

        assert result == st.SELECTING_SONG
        update.message.reply_text.assert_called_once()
        args, kwargs = update.message.reply_text.call_args
        assert "Wonderwall" in args[0]
        assert "reply_markup" in kwargs


@pytest.mark.asyncio
async def test_scenario_2_empty_search():
    """Сценарий 2. Поиск песни с пустым результатом (ничего не найдено)."""
    update = get_mock_update_message("Unexistent_Song_123")
    context = get_mock_context()

    mock_search_response = MagicMock()
    mock_search_response.json.return_value = {"results": []}
    mock_search_response.raise_for_status = MagicMock()

    with patch("src.database_utils.httpx.AsyncClient.post", new_callable=AsyncMock), \
            patch("src.api_utils.httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:

        mock_get.return_value = mock_search_response

        result = await search_audio_by_name(update, context)

        # Стейт не меняется (возвращается None)
        assert result is None
        # Проверяем текст сообщения
        update.message.reply_text.assert_called_with(
            'Ничего не получилось найти. Попробуйте написать еще раз.'
        )


@pytest.mark.asyncio
async def test_scenario_3_search_service_crash():
    """Сценарий 3. Отказоустойчивость при падении микросервиса поиска (Graceful Degradation)."""
    update = get_mock_update_message("Another Track")
    context = get_mock_context()

    with patch("src.database_utils.httpx.AsyncClient.post", new_callable=AsyncMock), \
            patch("src.api_utils.httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:

        # Эмулируем 500 ошибку сервера при поиске
        mock_get.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=MagicMock(), response=MagicMock())

        result = await search_audio_by_name(update, context)

        # Проверяем, что мок был вызван
        mock_get.assert_called_once()

        # Стейт не меняется, приложение не крашится
        assert result is None
        update.message.reply_text.assert_called_with(
            'Произошла ошибка. Попробуйте еще раз позже.'
        )


@pytest.mark.asyncio
async def test_scenario_4_select_song_menu():
    """Сценарий 4. Выбор песни из списка и формирование стартового меню."""
    update = get_mock_update_callback_query(data="track_123")
    context = get_mock_context()

    mock_track_info_response = MagicMock()
    mock_track_info_response.json.return_value = {
        "duration": 180000}  # 180 сек
    mock_track_info_response.raise_for_status = MagicMock()

    with patch("src.api_utils.httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_track_info_response

        result = await save_selected_audio(update, context)

        assert result == ConversationHandler.END
        # Данные сохранились в память сессии
        assert context.user_data[st.TRACK_ID] == "track_123"
        assert context.user_data[st.FILE_DURATION] == "180"
        assert context.user_data[st.DURATION_LEFT_BORDER] == "0"
        assert context.user_data[st.DURATION_RIGHT_BORDER] == "60"

        # Обновился текст сообщения
        update.callback_query.edit_message_text.assert_called_once()
        args, kwargs = update.callback_query.edit_message_text.call_args
        assert "Выберите опцию:" in args[0]
        assert "reply_markup" in kwargs


@pytest.mark.asyncio
async def test_scenario_5_db_failure_isolation():
    """Сценарий 5. Изоляция отказов базы данных (БД лежит, бот работает)."""
    update = get_mock_update_message("Valid Track")
    context = get_mock_context()

    mock_search_response = MagicMock()
    mock_search_response.json.return_value = {
        "results": [{"id": "1", "title": "Track", "artists": ["Art"], "duration": 120000, "url": "url"}]
    }
    mock_search_response.raise_for_status = MagicMock()

    with patch("src.database_utils.httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
            patch("src.api_utils.httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:

        # БД падает по таймауту
        mock_post.side_effect = httpx.RequestError("Connection refused")
        mock_get.return_value = mock_search_response

        result = await search_audio_by_name(update, context)

        # Несмотря на ошибку БД, процесс идет дальше
        assert result == st.SELECTING_SONG
        update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_scenario_6_custom_timecode():
    """Сценарий 6. Успешная установка произвольного таймкода (интеграция хендлера и валидатора)."""
    update = get_mock_update_message("30 75")
    context = get_mock_context()
    context.user_data[st.FILE_DURATION] = "200"

    result = await set_custom_time(update, context)

    # Проверка, что распарсены и применены корректные таймкоды
    assert result == ConversationHandler.END
    assert context.user_data[st.DURATION_LEFT_BORDER] == "30"
    assert context.user_data[st.DURATION_RIGHT_BORDER] == "75"

    update.message.reply_text.assert_called_once()
    assert "Возьмем аудио с 30с по 75с" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
@patch("src.handlers.api_utils.create_video", new_callable=AsyncMock)
@patch("src.handlers.api_utils.download_cover", new_callable=AsyncMock)
@patch("src.handlers.api_utils.trim_audio", new_callable=AsyncMock)
@patch("src.handlers.api_utils.download_track_stream", new_callable=AsyncMock)
async def test_scenario_7_create_video_happy_path(mock_stream, mock_trim, mock_cover, mock_video):
    """Сценарий 7. Интеграция цепочки микросервисов при создании видео (успешный путь)."""
    update = get_mock_update_callback_query()
    context = get_mock_context()

    # Подготовка данных пользователя
    context.user_data = {
        st.TRACK_ID: "123",
        st.DURATION_LEFT_BORDER: "0",
        st.DURATION_RIGHT_BORDER: "60",
        st.FILE_DURATION: "180"
    }

    # Мокаем успешное выполнение всех этапов
    mock_stream.return_value = "/tmp/audio.mp3"
    mock_trim.return_value = True
    mock_cover.return_value = "/tmp/cover.jpg"
    mock_video.return_value = True

    with tempfile.TemporaryDirectory() as temp_dir:
        mock_stream.return_value = os.path.join(temp_dir, "audio.mp3")
        mock_cover.return_value = os.path.join(temp_dir, "cover.jpg")

        with patch("src.handlers.conf.DOWNLOAD_FOLDER", temp_dir), \
                patch("src.handlers.db_utils.log_interaction", new_callable=AsyncMock):

            video_filename = f"video_123.mp4"
            video_file_path = os.path.join(temp_dir, video_filename)
            with open(video_file_path, "wb") as f:
                f.write(b"dummy video data")

            # Эмулируем функцию send_video_note от телеграма
            context.bot.send_video_note = AsyncMock()

            result = await create_video_message(update, context)

        # Вызовы прошли по цепочке успешно
        mock_stream.assert_called_once()
        mock_trim.assert_called_once()
        mock_cover.assert_called_once()
        mock_video.assert_called_once()
        context.bot.send_video_note.assert_called_once()


@pytest.mark.asyncio
@patch("src.handlers.api_utils.create_video", new_callable=AsyncMock)
@patch("src.handlers.api_utils.download_cover", new_callable=AsyncMock)
@patch("src.handlers.api_utils.trim_audio", new_callable=AsyncMock)
@patch("src.handlers.api_utils.download_track_stream", new_callable=AsyncMock)
async def test_scenario_8_trim_failure(mock_stream, mock_trim, mock_cover, mock_video):
    """Сценарий 8. Сбой на этапе обрезки аудио (прерывание цепочки)."""
    update = get_mock_update_callback_query()
    context = get_mock_context()

    context.user_data = {
        st.TRACK_ID: "123",
        st.DURATION_LEFT_BORDER: "100",  # Неверные таймкоды
        st.DURATION_RIGHT_BORDER: "50",
    }

    mock_stream.return_value = "/tmp/audio.mp3"
    # Сбой при выполнении запроса к media_processor
    mock_trim.return_value = False

    with patch("src.handlers.conf.DOWNLOAD_FOLDER", "/tmp"), \
            patch("src.handlers.db_utils.log_interaction", new_callable=AsyncMock):

        result = await create_video_message(update, context)

        # Обложка не качается, видео не рендерится
        mock_stream.assert_called_once()
        mock_trim.assert_called_once()
        mock_cover.assert_not_called()
        mock_video.assert_not_called()

        assert result == ConversationHandler.END
        # Пользователю отправлена ошибка
        kwargs = update.callback_query.edit_message_text.call_args.kwargs
        args = update.callback_query.edit_message_text.call_args.args
        called_text = kwargs.get('text', args[0] if args else '')
        assert "Ошибка, при создании кружка" in called_text


@pytest.mark.asyncio
@patch("src.handlers.api_utils.create_video", new_callable=AsyncMock)
@patch("src.handlers.api_utils.download_cover", new_callable=AsyncMock)
@patch("src.handlers.api_utils.trim_audio", new_callable=AsyncMock)
@patch("src.handlers.api_utils.download_track_stream", new_callable=AsyncMock)
async def test_scenario_9_cover_fallback(mock_stream, mock_trim, mock_cover, mock_video):
    """Сценарий 9. Использование локального фолбека при недоступности обложки аудио."""
    update = get_mock_update_callback_query()
    context = get_mock_context()

    context.user_data = {
        st.TRACK_ID: "123",
        st.DURATION_LEFT_BORDER: "0",
        st.DURATION_RIGHT_BORDER: "60",
    }

    mock_stream.return_value = "/tmp/audio.mp3"
    mock_trim.return_value = True
    # Скачивание обложки возвращает пустую строку (отказ сервиса)
    mock_cover.return_value = ""
    mock_video.return_value = True

    with patch("src.handlers.conf.DOWNLOAD_FOLDER", "/tmp"), \
            patch("src.handlers.db_utils.log_interaction", new_callable=AsyncMock):

        context.bot.send_video_note = AsyncMock()
        await create_video_message(update, context)

        # Процесс дошел до конца
        mock_video.assert_called_once()

        # Проверяем, что в create_video был передан дефолтный путь
        args, kwargs = mock_video.call_args
        if "image_path" in kwargs:
            assert kwargs["image_path"] == "video_note_images/vinyl_default.jpg"
        else:
            assert args[1] == "video_note_images/vinyl_default.jpg"


@pytest.mark.asyncio
async def test_scenario_10_restart_conversation_fallback():
    """Сценарий 10. Перезапуск процесса через /newsong (сброс памяти и стейта)."""
    update = get_mock_update_message("/newsong")
    context = get_mock_context()

    # Имитируем, что у пользователя заполнена сессия
    context.user_data = {
        st.TRACK_ID: "555",
        st.DURATION_LEFT_BORDER: "10",
        st.DURATION_RIGHT_BORDER: "20"
    }

    # В хендлере restart_conversation вызывается clear_user_data
    with patch('src.handlers.clear_user_data') as mock_clear:
        mock_clear.side_effect = lambda u, c: c.user_data.clear()

        result = await restart_conversation(update, context)

        # Проверяем, что стейт вернулся на старт
        assert result == st.TYPING_SONG_NAME

        # Память гарантированно очищена функциями очистки
        mock_clear.assert_called_once_with(update, context)
        assert len(context.user_data) == 0

        # Пользователю предложено ввести новую песню
        update.message.reply_text.assert_called_with(
            'Введите название песни для поиска:')
