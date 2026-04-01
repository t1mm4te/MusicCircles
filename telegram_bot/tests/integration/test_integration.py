import os
import pytest
import httpx
from unittest.mock import patch, AsyncMock, MagicMock, call
from telegram.ext import ConversationHandler
import tempfile

import src.states as st
import src.config as conf
import src.handlers as handlers
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


def get_mock_context():
    context = MagicMock()
    context.user_data = {}
    context.bot = AsyncMock()
    return context


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


@pytest.mark.asyncio
async def test_scenario_1_successful_search_audio():
    """Сценарий 1. Успешный поиск аудиозаписи. Бот выдает варианты."""
    update = get_mock_update_message("Borderline Tame Impala")
    context = get_mock_context()

    mock_db_response = MagicMock()
    mock_db_response.raise_for_status = MagicMock()

    mock_search_response = MagicMock()
    mock_search_response.json.return_value = {
        "results": [
            {
                "id": "1", "title": "Borderline", "artists": ["Tame Impala"],
                "duration": 238000
            }
        ]
    }
    mock_search_response.raise_for_status = MagicMock()

    with (
        patch("src.database_utils.httpx.AsyncClient.post",
              new_callable=AsyncMock) as mock_post,
        patch("src.api_utils.httpx.AsyncClient.get",
              new_callable=AsyncMock) as mock_get
    ):

        mock_post.return_value = mock_db_response
        mock_get.return_value = mock_search_response

        result = await search_audio_by_name(update, context)

        mock_post.assert_called_once_with(
            f"{conf.DATABASE_API_URL}/log-interaction/",
            json={
                "user_id": 123,
                "username": "test_user",
                "interaction_type": "Поиск песни"
            },
            timeout=10.0
        )
        mock_db_response.raise_for_status.assert_called_once()

        mock_get.assert_called_once_with(
            f"{conf.AUDIO_RECEIVER_API_URL}/search/",
            params={"query": "Borderline Tame Impala"},
            timeout=10.0
        )
        mock_search_response.raise_for_status.assert_called_once()

        assert result == st.SELECTING_SONG
        update.message.reply_text.assert_called_once()
        args, kwargs = update.message.reply_text.call_args
        assert args[0].startswith("Выбери одну песню из найденных:")
        assert "Borderline" in args[0]
        assert "Tame Impala" in args[0]
        assert "3:58" in args[0]
        assert "reply_markup" in kwargs

        keyboard = kwargs["reply_markup"].inline_keyboard
        assert len(keyboard) >= 1  # Хотя бы один ряд кнопок
        assert len(keyboard[0]) == 1  # В первом ряду одна кнопка
        assert keyboard[0][0].text == "1"  # Порядковый номер трека
        assert keyboard[0][0].callback_data == "1"  # ID трека


@pytest.mark.asyncio
async def test_scenario_2_empty_search():
    """Сценарий 2. Поиск песни с пустым результатом (ничего не найдено)."""
    update = get_mock_update_message("some song")
    context = get_mock_context()

    mock_db_response = MagicMock()
    mock_db_response.raise_for_status = MagicMock()

    mock_search_response = MagicMock()
    mock_search_response.json.return_value = {"results": []}
    mock_search_response.raise_for_status = MagicMock()

    with (
        patch("src.database_utils.httpx.AsyncClient.post",
              new_callable=AsyncMock) as mock_post,
        patch("src.api_utils.httpx.AsyncClient.get",
              new_callable=AsyncMock) as mock_get
    ):

        mock_post.return_value = mock_db_response
        mock_get.return_value = mock_search_response

        result = await search_audio_by_name(update, context)

        mock_post.assert_called_once_with(
            f"{conf.DATABASE_API_URL}/log-interaction/",
            json={
                "user_id": 123,
                "username": "test_user",
                "interaction_type": "Поиск песни"
            },
            timeout=10.0
        )
        mock_db_response.raise_for_status.assert_called_once()

        mock_get.assert_called_once_with(
            f"{conf.AUDIO_RECEIVER_API_URL}/search/",
            params={"query": "some song"},
            timeout=10.0
        )
        mock_search_response.raise_for_status.assert_called_once()

        # Стейт не меняется (возвращается None)
        assert result is None
        # Проверяем текст сообщения
        update.message.reply_text.assert_called_once_with(
            'Ничего не получилось найти. Попробуйте написать еще раз.'
        )
        _, kwargs = update.message.reply_text.call_args
        assert "reply_markup" not in kwargs
        assert context.user_data == {}


@pytest.mark.asyncio
async def test_scenario_3_search_service_crash():
    """Сценарий 3. Отказоустойчивость при падении микросервиса поиска."""
    update = get_mock_update_message("Another Track")
    context = get_mock_context()

    mock_db_response = MagicMock()
    mock_db_response.raise_for_status = MagicMock()

    with (
        patch("src.database_utils.httpx.AsyncClient.post",
              new_callable=AsyncMock) as mock_post,
        patch("src.api_utils.httpx.AsyncClient.get",
              new_callable=AsyncMock) as mock_get
    ):

        mock_post.return_value = mock_db_response

        mock_error_response = MagicMock()
        mock_error_response.status_code = 500
        mock_error_response.text = "Internal Server Error"
        mock_get.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=MagicMock(), response=mock_error_response)

        result = await search_audio_by_name(update, context)

        mock_post.assert_called_once_with(
            f"{conf.DATABASE_API_URL}/log-interaction/",
            json={
                "user_id": 123,
                "username": "test_user",
                "interaction_type": "Поиск песни"
            },
            timeout=10.0
        )
        mock_db_response.raise_for_status.assert_called_once()

        mock_get.assert_called_once_with(
            f"{conf.AUDIO_RECEIVER_API_URL}/search/",
            params={"query": "Another Track"},
            timeout=10.0
        )

        # Стейт не меняется, приложение не крашится
        assert result is None
        update.message.reply_text.assert_called_once_with(
            'Произошла ошибка. Попробуйте еще раз позже.'
        )
        _, kwargs = update.message.reply_text.call_args
        assert "reply_markup" not in kwargs
        assert context.user_data == {}


@pytest.mark.asyncio
async def test_scenario_4_select_song_menu():
    """Сценарий 4. Выбор песни из списка и формирование стартового меню."""
    update = get_mock_update_callback_query(data="track_123")
    context = get_mock_context()

    mock_track_info_response = MagicMock()
    mock_track_info_response.json.return_value = {
        "duration": 180000}  # 180 сек
    mock_track_info_response.raise_for_status = MagicMock()

    with (
        patch("src.api_utils.httpx.AsyncClient.get", new_callable=AsyncMock)
        as mock_get
    ):
        mock_get.return_value = mock_track_info_response

        result = await save_selected_audio(update, context)

        update.callback_query.answer.assert_called_once()
        mock_get.assert_called_once_with(
            f"{conf.AUDIO_RECEIVER_API_URL}/track/track_123/info",
            timeout=10.0
        )
        mock_track_info_response.raise_for_status.assert_called_once()

        assert result == ConversationHandler.END
        # Данные сохранились в память сессии
        assert context.user_data[st.TRACK_ID] == "track_123"
        assert context.user_data[st.FILE_DURATION] == "180"
        assert context.user_data[st.DURATION_LEFT_BORDER] == "0"
        assert context.user_data[st.DURATION_RIGHT_BORDER] == "60"

        # Обновился текст сообщения
        update.callback_query.edit_message_text.assert_called_once()
        args, kwargs = update.callback_query.edit_message_text.call_args
        assert args[0] == "Выберите опцию:"
        assert "reply_markup" in kwargs

        menu = kwargs["reply_markup"].inline_keyboard
        assert len(menu) == 3
        assert len(menu[0]) == 1
        assert len(menu[1]) == 1
        assert len(menu[2]) == 1


@pytest.mark.asyncio
async def test_scenario_5_db_failure_isolation():
    """Сценарий 5. Изоляция отказов базы данных."""
    update = get_mock_update_message("Valid Track")
    context = get_mock_context()

    mock_search_response = MagicMock()
    mock_search_response.json.return_value = {
        "results": [
            {
                "id": "1", "title": "Borderline", "artists": ["Tame Impala"],
                "duration": 238000
            }
        ]
    }
    mock_search_response.raise_for_status = MagicMock()

    with (
        patch("src.database_utils.httpx.AsyncClient.post",
              new_callable=AsyncMock) as mock_post,
        patch("src.api_utils.httpx.AsyncClient.get",
              new_callable=AsyncMock) as mock_get
    ):
        # БД падает
        mock_post.side_effect = httpx.RequestError("Connection refused")
        mock_get.return_value = mock_search_response

        result = await search_audio_by_name(update, context)

        mock_post.assert_called_once_with(
            f"{conf.DATABASE_API_URL}/log-interaction/",
            json={
                "user_id": 123,
                "username": "test_user",
                "interaction_type": "Поиск песни"
            },
            timeout=10.0
        )
        mock_get.assert_called_once_with(
            f"{conf.AUDIO_RECEIVER_API_URL}/search/",
            params={"query": "Valid Track"},
            timeout=10.0
        )
        mock_search_response.raise_for_status.assert_called_once()

        # Несмотря на ошибку БД, процесс идет дальше
        assert result == st.SELECTING_SONG
        update.message.reply_text.assert_called_once()
        args, kwargs = update.message.reply_text.call_args
        assert "Borderline" in args[0]
        assert "reply_markup" in kwargs


@pytest.mark.asyncio
async def test_scenario_6_custom_timecode():
    """Сценарий 6. Успешная установка произвольного таймкода."""
    update = get_mock_update_message("30 75")
    context = get_mock_context()
    context.user_data[st.FILE_DURATION] = "200"

    with patch("src.handlers.get_seconds", wraps=handlers.get_seconds) as mock_get_seconds:
        result = await set_custom_time(update, context)

    mock_get_seconds.assert_has_calls([call("30"), call("75")])
    assert mock_get_seconds.call_count == 2

    # Проверка, что распарсены и применены корректные таймкоды
    assert result == ConversationHandler.END
    assert context.user_data[st.DURATION_LEFT_BORDER] == "30"
    assert context.user_data[st.DURATION_RIGHT_BORDER] == "75"

    update.message.reply_text.assert_called_once()
    args, kwargs = update.message.reply_text.call_args
    assert "с 30с по 75с." in args[0]
    assert "Выберите опцию:" in args[0]
    assert "reply_markup" in kwargs

    menu = kwargs["reply_markup"].inline_keyboard
    assert len(menu) == 3


@pytest.mark.asyncio
@patch("src.handlers.api_utils.create_video", new_callable=AsyncMock)
@patch("src.handlers.api_utils.download_cover", new_callable=AsyncMock)
@patch("src.handlers.api_utils.trim_audio", new_callable=AsyncMock)
@patch("src.handlers.api_utils.download_track_stream", new_callable=AsyncMock)
async def test_scenario_7_create_video_happy_path(mock_stream, mock_trim,
                                                  mock_cover, mock_video):
    """Сценарий 7. Интеграция цепочки микросервисов при создании видео"""
    update = get_mock_update_callback_query()
    context = get_mock_context()

    context.user_data = {
        st.TRACK_ID: "123",
        st.DURATION_LEFT_BORDER: "0",
        st.DURATION_RIGHT_BORDER: "60",
        st.FILE_DURATION: "180"
    }

    mock_stream.return_value = "/tmp/audio.mp3"
    mock_trim.return_value = True
    mock_cover.return_value = "/tmp/cover.jpg"
    mock_video.return_value = True

    with tempfile.TemporaryDirectory() as temp_dir:
        mock_stream.return_value = os.path.join(temp_dir, "audio.mp3")
        mock_cover.return_value = os.path.join(temp_dir, "cover.jpg")

        with (
            patch("src.handlers.conf.DOWNLOAD_FOLDER", temp_dir),
            patch("src.handlers.db_utils.log_interaction",
                  new_callable=AsyncMock) as mock_log_interaction
        ):

            video_filename = "video_123.mp4"
            video_file_path = os.path.join(temp_dir, video_filename)
            with open(video_file_path, "wb") as f:
                f.write(b"dummy video data")

            context.bot.send_video_note = AsyncMock()

            result = await create_video_message(update, context)

        mock_log_interaction.assert_called_once_with(
            user_id=123,
            username="test_user",
            interaction_type='Создание видео'
        )

        mock_stream.assert_called_once()
        mock_stream.assert_called_once_with(
            track_id="123",
            save_dir=temp_dir
        )

        mock_trim.assert_called_once()
        mock_trim.assert_called_once_with(
            file_path=os.path.join(temp_dir, "audio.mp3"),
            start=0,
            end=60,
            output_path=f"{temp_dir}/trimmed_123.mp3"
        )

        mock_cover.assert_called_once()
        mock_cover.assert_called_once_with(
            track_id="123",
            save_dir=temp_dir
        )

        mock_video.assert_called_once()
        mock_video.assert_called_once_with(
            audio_path=f"{temp_dir}/trimmed_123.mp3",
            image_path=os.path.join(temp_dir, "cover.jpg"),
            output_path=f"{temp_dir}/video_123.mp4"
        )

        context.bot.send_video_note.assert_called_once()
        _, send_kwargs = context.bot.send_video_note.call_args
        assert send_kwargs["chat_id"] == 456
        assert send_kwargs["video_note"] is not None

        assert update.callback_query.answer.call_count == 1
        assert update.callback_query.edit_message_text.call_count == 4
        assert result == ConversationHandler.END
        assert context.user_data == {}


@pytest.mark.asyncio
@patch("src.handlers.api_utils.create_video", new_callable=AsyncMock)
@patch("src.handlers.api_utils.download_cover", new_callable=AsyncMock)
@patch("src.handlers.api_utils.trim_audio", new_callable=AsyncMock)
@patch("src.handlers.api_utils.download_track_stream", new_callable=AsyncMock)
async def test_scenario_8_trim_failure(mock_stream, mock_trim, mock_cover,
                                       mock_video):
    """Сценарий 8. Сбой на этапе обрезки аудио."""
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

    with (
        patch("src.handlers.conf.DOWNLOAD_FOLDER", "/tmp"),
        patch("src.handlers.db_utils.log_interaction",
              new_callable=AsyncMock) as mock_log_interaction
    ):

        context.bot.send_video_note = AsyncMock()

        result = await create_video_message(update, context)

        mock_log_interaction.assert_called_once_with(
            user_id=123,
            username="test_user",
            interaction_type='Создание видео'
        )

        # Обложка не качается, видео не рендерится
        mock_stream.assert_called_once_with(
            track_id="123",
            save_dir="/tmp"
        )
        mock_trim.assert_called_once_with(
            file_path="/tmp/audio.mp3",
            start=100,
            end=50,
            output_path="/tmp/trimmed_123.mp3"
        )
        mock_cover.assert_not_called()
        mock_video.assert_not_called()
        context.bot.send_video_note.assert_not_called()

        update.callback_query.answer.assert_called_once()
        assert update.callback_query.edit_message_text.call_count == 3

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
async def test_scenario_9_cover_fallback(mock_stream, mock_trim, mock_cover,
                                         mock_video):
    """
    Сценарий 9. Использование стандартного изображения при недоступности
    обложки аудио.
    """
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

    with tempfile.TemporaryDirectory() as temp_dir:
        mock_stream.return_value = os.path.join(temp_dir, "audio.mp3")

        with patch("src.handlers.conf.DOWNLOAD_FOLDER", temp_dir), \
                patch("src.handlers.db_utils.log_interaction",
                      new_callable=AsyncMock) as mock_log_interaction:

            video_file_path = os.path.join(temp_dir, "video_123.mp4")
            with open(video_file_path, "wb") as f:
                f.write(b"dummy video data")

            context.bot.send_video_note = AsyncMock()
            result = await create_video_message(update, context)

            mock_log_interaction.assert_called_once_with(
                user_id=123,
                username="test_user",
                interaction_type='Создание видео'
            )

            mock_stream.assert_called_once_with(
                track_id="123",
                save_dir=temp_dir
            )
            mock_trim.assert_called_once_with(
                file_path=os.path.join(temp_dir, "audio.mp3"),
                start=0,
                end=60,
                output_path=f"{temp_dir}/trimmed_123.mp3"
            )
            mock_cover.assert_called_once_with(
                track_id="123",
                save_dir=temp_dir
            )

            # Проверяем, что в create_video был передан дефолтный путь
            mock_video.assert_called_once_with(
                audio_path=f"{temp_dir}/trimmed_123.mp3",
                image_path="video_note_images/vinyl_default.jpg",
                output_path=f"{temp_dir}/video_123.mp4"
            )

            context.bot.send_video_note.assert_called_once()
            _, send_kwargs = context.bot.send_video_note.call_args
            assert send_kwargs["chat_id"] == 456
            assert send_kwargs["video_note"] is not None

            update.callback_query.answer.assert_called_once()
            assert update.callback_query.edit_message_text.call_count == 4
            assert result == ConversationHandler.END
            assert context.user_data == {}


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
        mock_clear.side_effect = (
            lambda update, context: context.user_data.clear()
        )

        result = await restart_conversation(update, context)

        # Проверяем, что стейт вернулся на старт
        assert result == st.TYPING_SONG_NAME

        # Память гарантированно очищена функциями очистки
        mock_clear.assert_called_once_with(update, context)
        assert context.user_data == {}

        # Пользователю предложено ввести новую песню
        update.message.reply_text.assert_called_once_with(
            'Введите название песни для поиска:')

        # Для команды /newsong должна использоваться ветка message,
        # а не callback.
        assert update.callback_query.answer.call_count == 0
        assert update.callback_query.edit_message_text.call_count == 0
