import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)

import src.states as st
import src.config as conf
import src.api_utils as api_utils
import src.database_utils as db_utils


logger = logging.getLogger(__name__)


MAX_VIDEO_NOTE_DURATION_SECONDS = 55


async def start(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Печатает приветственное сообщение.
    """
    clear_user_data(update, context)

    assert update.message is not None
    assert update.message.from_user is not None

    user = update.message.from_user
    logger.info(f'{user.id} started bot')

    await update.message.reply_text(
        'Привет, я бот, который создает музыкальные кружочки.\n'
        'Напиши мне название песни.'
    )


# Fallbacks command handler.
async def restart_conversation(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
) -> str:
    """
    Перезапускает диалог для поиска новой песни.
    """
    clear_user_data(update, context)

    TEXT = 'Введите название песни для поиска:'

    if update.message:
        await update.message.reply_text(TEXT)

    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(TEXT)

    return st.TYPING_SONG_NAME


def get_main_menu(
        context: ContextTypes.DEFAULT_TYPE
) -> InlineKeyboardMarkup:
    """
    Возвращает основное меню.

    :param context: Контекст для получения уже установленных настроек.

    :return: Разметка клавиатуры, являющейся меню.
    """
    assert context.user_data is not None

    user_data = context.user_data

    time_code_message = ('⏱️Редактировать время: с '
                         f'{user_data[st.DURATION_LEFT_BORDER]}с '
                         f'по {user_data[st.DURATION_RIGHT_BORDER]}с')

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    time_code_message,
                    callback_data=st.SET_TIME_CODE
                ),
            ],
            [
                InlineKeyboardButton(
                    '▶️Создать кружок',
                    callback_data=st.CREATE_VIDEO_MESSAGE
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔄 Найти новую песню",
                    callback_data=str(st.RESTART_SEARCH)
                ),
            ],
        ]
    )

    return keyboard


# ENTRY_POINT
async def save_audio(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
) -> str | None:
    """
    Проверка аудио и запоминание file_id.
    Показ меню для выбора опций.
    """
    assert update.message is not None

    message = update.message

    # Проверяем, что пришел именно аудиофайл
    audio = message.audio or message.voice
    if not audio:
        await message.reply_text('Отправьте аудиофайл (MP3, OGG, WAV).')
        return None

    # Получаем информацию о файле
    file_id = audio.file_id

    assert audio.file_size is not None

    file_size = audio.file_size  # Размер в байтах
    # MIME-тип, например 'audio/mpeg' для mp3 и 'audio/ogg' для голосовых
    mime_type = audio.mime_type

    # Ограничения по размеру (например, 6MB)
    max_file_size = 6 * 1024 * 1024  # 6 MB
    if file_size > max_file_size:
        await message.reply_text(
            f'Файл слишком большой: {file_size / 1024 / 1024:.2f} MB! '
            'Максимальный размер – 6MB.'
        )
        return None

    # Проверяем допустимые MIME-типы
    allowed_mime = {'audio/mpeg', 'audio/ogg', 'audio/wav'}
    if mime_type not in allowed_mime:
        await message.reply_text(
            'Неподдерживаемый формат! Используйте MP3, OGG, WAV.'
        )
        return None

    assert context.user_data is not None

    user_data = context.user_data

    file_duration = audio.duration
    user_data[st.FILE_DURATION] = str(file_duration)

    file_name_extension = get_file_name_extension(mime_type)
    file_name = file_id + file_name_extension

    # Скачиваем файл
    file = await context.bot.get_file(file_id)

    assert conf.DOWNLOAD_FOLDER is not None

    file_path = os.path.join(conf.DOWNLOAD_FOLDER, f'{file_name}')
    user_data[st.TRACK_ID] = file_id
    user_data[st.TRACK_FILE_PATH] = file_path
    os.makedirs(conf.DOWNLOAD_FOLDER, exist_ok=True)

    await file.download_to_drive(file_path)

    logger.info(f'Файл сохранён: Размер - {file_size} Путь - {file_path}')

    await message.reply_text('Файл загружен!')

    # Настройки по умолчанию, после вынести в отдельный метод.
    user_data[st.DURATION_LEFT_BORDER] = str(0)
    user_data[st.DURATION_RIGHT_BORDER] = str(
        min(MAX_VIDEO_NOTE_DURATION_SECONDS, file_duration)
    )

    keyboard = get_main_menu(context)

    await message.reply_text('Выберите опцию:', reply_markup=keyboard)

    return st.CHOOSING_OPTIONS


# ENTRY POINT / TYPING_SONG_NAME
async def search_audio_by_name(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
) -> str | None:
    """
    Ищет песню по названию, введенному пользователем,
    и выдает список возможных вариантов
    и соответствующие им кнопки для выбора.
    """
    assert update.message is not None
    assert update.message.text is not None

    track_name = update.message.text
    user = update.message.from_user
    assert user is not None

    logger.info(f'User {user.id} searching for: {track_name}')

    is_logged = await db_utils.log_interaction(
        user_id=user.id,
        username=user.username,
        interaction_type='Поиск песни'
    )

    if not is_logged:
        logger.error(
            f'Не удалось залогировать взаимодействие пользователя {user.id} '
            'при поиске песни.'
        )

    tracks = await api_utils.search_for_tracks(
        track_name=track_name
    )

    if tracks is None:
        await update.message.reply_text(
            'Произошла ошибка. Попробуйте еще раз позже.'
        )
        return None

    if not tracks:
        await update.message.reply_text(
            'Ничего не получилось найти. Попробуйте написать еще раз.'
        )
        return None

    text = 'Выбери одну песню из найденных:'
    inline_keyboards = []
    for i, track in enumerate(tracks, start=1):
        text += (f'\n {i}) {track.title} – {track.artists} '
                 f'({track.duration // 60}:{track.duration % 60})')

        inline_keyboards.append(
            InlineKeyboardButton(
                str(i),
                callback_data=str(track.id))
        )

    keyboard = [
        inline_keyboards[:1],
        inline_keyboards[1:]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text,
        reply_markup=reply_markup
    )

    return st.SELECTING_SONG


# SELECTING_SONG
async def save_selected_audio(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
) -> int | str:
    """Сохраняет песню по id из callback query."""

    assert update.callback_query is not None

    query = update.callback_query
    assert query.data is not None
    await query.answer()

    assert context.user_data is not None

    track_id = query.data
    duration = await api_utils.get_track_info(track_id=track_id)

    if not duration:
        await query.edit_message_text(
            'Произошла ошибка. Попробуйте написать название песни заново.'
        )
        return st.TYPING_SONG_NAME

    user_data = context.user_data

    user_data[st.TRACK_ID] = track_id
    user_data[st.FILE_DURATION] = str(duration)
    user_data[st.DURATION_LEFT_BORDER] = str(0)
    user_data[st.DURATION_RIGHT_BORDER] = str(
        min(MAX_VIDEO_NOTE_DURATION_SECONDS, duration)
    )

    keyboard = get_main_menu(context)

    await query.edit_message_text(
        'Выберите опцию:',
        reply_markup=keyboard
    )

    return ConversationHandler.END


def get_file_name_extension(mime: str) -> str:
    """
    Возвращает тип файла исходя из MIME-типов.

    :param mime: MIME-тип.

    :return: Расширение имени файла.
    """
    match mime:
        case 'audio/mpeg':
            return '.mp3'
        case 'audio/ogg':
            return '.ogg'
        case 'audio/x-wav':
            return '.wav'
        case _:
            return ''


# ENTRY POINT
async def print_time_codes(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
) -> str:
    """
    Показывает меню для установки времени.
    """
    assert update.callback_query is not None

    query = update.callback_query
    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton('⭐️С начала',
                                 callback_data=st.DURATION_START),
            InlineKeyboardButton('Ввести время самому',
                                 callback_data=st.DURATION_CUSTOM),
        ],
        [
            InlineKeyboardButton('Назад', callback_data=st.BACK_TO_MENU),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    assert context.user_data is not None

    audio_duration = context.user_data[st.FILE_DURATION]

    await query.edit_message_text(
        f'Теперь давай обрежем твой аудиофайл как надо!\n'
        f'Его длительность {audio_duration}с. '
        'Максимальная длина кружочка - '
        f'{MAX_VIDEO_NOTE_DURATION_SECONDS} секунд. '
        'Можем начать с начала или выбрать особый отрезок песни.',
        reply_markup=reply_markup
    )

    return st.SELECTING_ACTION


# SELECTING_ACTION
async def set_start_time(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Устанавливает время по умолчанию - с начала.
    """
    assert update.callback_query is not None

    query = update.callback_query
    await query.answer()

    assert context.user_data is not None

    context.user_data[st.DURATION_LEFT_BORDER] = str(0)
    context.user_data[st.DURATION_RIGHT_BORDER] = str(
        min(
            MAX_VIDEO_NOTE_DURATION_SECONDS,
            int(context.user_data[st.FILE_DURATION])
        )
    )

    keyboard = get_main_menu(context)

    await query.edit_message_text(
        '✅Будем отсчитывать сначала.\nВыберите опцию:',
        reply_markup=keyboard
    )

    return ConversationHandler.END


# SELECTING_ACTION
async def print_custom_time_text(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
) -> str:
    """
    Печатает текст для установки собственного времени.
    """
    assert update.callback_query is not None

    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        'Хорошо, задай время или в формате мм:сс или сс для '
        'обозначения начала, или мм:сс мм:сс или сс сс для '
        'обозначения интервалов (через пробел).'
    )

    return st.INPUT_TIME_CODE


# INPUT_TIME_CODE
async def set_custom_time(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
) -> int | str:
    """
    Принимает сообщение с указанием времени, запоминает его и возвращает меню.
    """
    assert update.message is not None
    assert update.message.text is not None

    text = update.message.text
    time_values = text.split()

    if len(time_values) not in (1, 2):
        await update.message.reply_text(
            'Ошибка в формате времени. '
            'Укажите время в виде "мм:сс" или "мм:сс мм:сс".'
        )
        return st.INPUT_TIME_CODE

    try:
        time_codes = tuple(map(get_seconds, time_values))
    except ValueError:
        await update.message.reply_text(
            'Ошибка в формате времени. '
            'Укажите время в виде "мм:сс" или "мм:сс мм:сс".'
        )
        return st.INPUT_TIME_CODE

    assert context.user_data is not None

    user_data = context.user_data

    file_duration = int(user_data[st.FILE_DURATION])
    left_border = time_codes[0]

    if len(time_codes) == 2:
        right_border = time_codes[1]
    else:
        right_border = min(
            left_border + MAX_VIDEO_NOTE_DURATION_SECONDS,
            file_duration
        )

    if left_border < 0 or right_border < 0:
        await update.message.reply_text(
            'Ошибка валидации времени. Значения должны быть положительными.'
        )
        return st.INPUT_TIME_CODE

    if left_border >= right_border:
        await update.message.reply_text(
            'Ошибка валидации времени. '
            'Начало интервала должно быть меньше конца.'
        )
        return st.INPUT_TIME_CODE

    if right_border > file_duration:
        await update.message.reply_text(
            'Ошибка валидации времени. Интервал выходит за пределы трека.'
        )
        return st.INPUT_TIME_CODE

    if right_border - left_border > MAX_VIDEO_NOTE_DURATION_SECONDS:
        await update.message.reply_text(
            'Ошибка валидации времени. Длина интервала не должна превышать '
            f'{MAX_VIDEO_NOTE_DURATION_SECONDS} секунд.'
        )
        return st.INPUT_TIME_CODE

    user_data[st.DURATION_LEFT_BORDER] = str(left_border)
    user_data[st.DURATION_RIGHT_BORDER] = str(right_border)

    keyboard = get_main_menu(context)

    await update.message.reply_text(
        f'✅Возьмем аудио с {context.user_data[st.DURATION_LEFT_BORDER]}с по '
        f'{context.user_data[st.DURATION_RIGHT_BORDER]}с.\nВыберите опцию:',
        reply_markup=keyboard
    )

    return ConversationHandler.END


def get_seconds(time: str) -> int:
    """
    Получение секунд из строки, являющейся временем.

    :param time: Время в виде mm:ss или ss.

    :return: Время в секундах.
    """
    if ':' in time:
        m, s = map(int, time.split(':'))
        return m * 60 + s
    return int(time)


# SELECTING_ACTION
async def back_to_menu(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Возвращает меню.
    """
    assert update.callback_query is not None

    query = update.callback_query
    await query.answer()

    keyboard = get_main_menu(context)

    await query.edit_message_text(
        'Выберите опцию:',
        reply_markup=keyboard
    )

    return ConversationHandler.END


# CHOOSING_OPTIONS
async def create_video_message(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Создает видео сообщение из ранее полученных данных.
    """
    assert update.callback_query is not None
    assert update.effective_chat is not None
    assert context.user_data is not None
    assert conf.DOWNLOAD_FOLDER is not None

    query = update.callback_query
    await query.answer()

    user = update.callback_query.from_user
    await db_utils.log_interaction(
        user_id=user.id,
        username=user.username,
        interaction_type='Создание видео'
    )

    video_note_processing_message = (
        'Хорошо, создаю кружок...\n'
        '⚙️'
    )
    await query.edit_message_text(
        text=video_note_processing_message
    )

    bot = context.bot
    chat_id = update.effective_chat.id
    user_data = context.user_data

    track_id = user_data[st.TRACK_ID]

    ERROR_MESSAGE_TO_USER = 'Ошибка, при создании кружка 😢'

    # MP3 FILE DOWNLOADING.

    assert conf.DOWNLOAD_FOLDER is not None

    file_path = await api_utils.download_track_stream(
        track_id=track_id,
        save_dir=conf.DOWNLOAD_FOLDER
    )

    user_data[st.TRACK_FILE_PATH] = file_path

    logger.info(f'Файл загружен: {file_path}')

    video_note_processing_message += '⚙️'
    await query.edit_message_text(
        text=video_note_processing_message
    )

    # AUDIO TRIMMING.

    output_audio_file_path = f'{conf.DOWNLOAD_FOLDER}/trimmed_{track_id}.mp3'

    logger.info(
        'Prepairing for trimming audio: '
        f'{user_data[st.TRACK_FILE_PATH]=} '
        f'{int(user_data[st.DURATION_LEFT_BORDER])=} '
        f'{int(user_data[st.DURATION_RIGHT_BORDER])=} '
        f'{output_audio_file_path=}'
    )

    is_audio_trimmed = await api_utils.trim_audio(
        file_path=user_data[st.TRACK_FILE_PATH],
        start=int(user_data[st.DURATION_LEFT_BORDER]),
        end=int(user_data[st.DURATION_RIGHT_BORDER]),
        output_path=output_audio_file_path
    )

    if not is_audio_trimmed:
        logger.warning(
            'Не удалось обрезать аудио.'
        )
        await query.edit_message_text(
            text=ERROR_MESSAGE_TO_USER
        )
        return ConversationHandler.END

    video_note_processing_message += '⚙️'
    await query.edit_message_text(
        text=video_note_processing_message
    )

    # COVER DOWNLOADING.

    cover_file_path = await api_utils.download_cover(
        track_id=track_id,
        save_dir=conf.DOWNLOAD_FOLDER
    )

    if not cover_file_path:
        logger.warning(
            f'Не удалось скачать обложку для трека {track_id}. '
            'Используется обложка по умолчанию.'
        )
        cover_file_path = 'video_note_images/vinyl_default.jpg'

    video_note_processing_message += '⚙️'
    await query.edit_message_text(
        text=video_note_processing_message
    )

    # VIDEO CREATION.

    output_video_file_path = f'{conf.DOWNLOAD_FOLDER}/video_{track_id}.mp4'

    logger.info(
        'Prepairing for trimming audio: '
        f'{output_video_file_path=} '
        f'{cover_file_path=} '
        f'{output_audio_file_path=}'
    )

    is_video_created = await api_utils.create_video(
        audio_path=output_audio_file_path,
        image_path=cover_file_path,
        output_path=output_video_file_path
    )

    logger.info(f'Список файлов: {os.listdir(path=conf.DOWNLOAD_FOLDER)}')

    if not is_video_created:
        logger.error('Ошибка при создании видео-кружка.')
        await query.edit_message_text(
            text=ERROR_MESSAGE_TO_USER
        )
        return ConversationHandler.END

    if not os.path.exists(output_video_file_path):
        logger.error(f'Файл видео не найден по пути: {output_video_file_path}')
        await query.edit_message_text(
            text=ERROR_MESSAGE_TO_USER
        )
        return ConversationHandler.END

    try:
        logger.info(f'Попытка отправить видео-кружок в chat_id: {chat_id}')

        with open(output_video_file_path, 'rb') as video_file:
            await bot.send_video_note(
                chat_id=chat_id,
                video_note=video_file,
            )

        logger.info('Видео-кружок успешно отправлен!')

    except BadRequest as e:
        logger.error(f'Ошибка Telegram (BadRequest): {e}')
        error_message = f'Не удалось отправить видео-кружок: {e.message}'

        if ('wrong file identifier' in str(e).lower()
                or 'can\'t parse url' in str(e).lower()):
            error_message += ('\nВозможно, неверный формат файла, '
                              'URL или file_id.')
        elif 'chat not found' in str(e).lower():
            error_message += ('\nПроверьте правильность '
                              f'TARGET_CHAT_ID ({chat_id}).')
        elif 'VIDEO_NOTE_DIMENSIONS_INVALID' in str(e):
            error_message += '\nВидео должно быть квадратным.'

        logger.error(error_message)

    except TelegramError as e:
        logger.error(f'Общая ошибка Telegram: {e}')

    except Exception as e:
        logger.error(f'Неожиданная ошибка: {e}')

    clear_user_data(update, context)
    return ConversationHandler.END


def clear_user_data(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Удаляет загруженный файл, очищает user_data.
    """
    if update.message:
        assert update.message.from_user is not None

        user_info = (f'{update.message.from_user.id} - '
                     f'{update.message.from_user.username}')
    else:
        assert update.callback_query is not None

        user_info = (f'{update.callback_query.from_user.id} - '
                     f'{update.callback_query.from_user.username}')

    assert context.user_data is not None

    user_data = context.user_data

    if user_data.get(st.TRACK_FILE_PATH):
        path = user_data[st.TRACK_FILE_PATH]
        if os.path.exists(path):
            os.remove(path)
            logger.info(f'{user_info}: File {path} has been deleted')
        else:
            logger.info(f'{user_info}: File {path} has already been deleted')

    user_data.clear()

    logger.info(f'{user_info}: user_data has been cleared')
