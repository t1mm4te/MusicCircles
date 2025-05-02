import logging
import os
import httpx

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)

import src.states as st

import src.config as conf


logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Печатает приветственное сообщение.
    """
    assert update.message is not None
    assert update.message.from_user is not None

    user = update.message.from_user
    logger.info(f'{user.id} started bot')

    await update.message.reply_text(
        'Привет, я бот, который создает музыкальные кружочки.\n'
        'Пришли мне файл с твоей песней или голосовое сообщение'
    )


def get_main_menu(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
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
                    callback_data=st.SET_TIME_CODE),
            ],
            [
                InlineKeyboardButton(
                    '▶️Создать кружок',
                    callback_data=st.CREATE_VIDEO_MESSAGE),
            ],
        ]
    )

    return keyboard


# ENTRY_POINT
async def save_audio(update: Update,
                     context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """
    Проверка аудио и запоминание file_id.
    Показ меню для выбора опций.
    """
    clear(update, context)

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
    user_data[st.MP3_FILE_PATH] = file_path
    os.makedirs(conf.DOWNLOAD_FOLDER, exist_ok=True)

    await file.download_to_drive(file_path)

    logger.info(f'Файл сохранён: Размер - {file_size} Путь - {file_path}')

    await message.reply_text('Файл загружен!')

    # Настройки по умолчанию, после вынести в отдельный метод.
    user_data[st.DURATION_LEFT_BORDER] = str(0)
    user_data[st.DURATION_RIGHT_BORDER] = str(min(60, file_duration))

    keyboard = get_main_menu(context)

    await message.reply_text('Выберите опцию:', reply_markup=keyboard)

    return st.CHOOSING_OPTIONS


async def search_audio_by_name(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """
    Ищет песню по названию, введенному пользователем,
    и выдает список возможных вариантов
    и соответствующие им кнопки для выбора.
    """
    assert update.message is not None
    assert update.message.text is not None

    song_name = update.message.text
    logger.info(song_name)

    url = f'{conf.AUDIO_RECEIVER_API_URL}/search/'
    params = {'query': song_name}

    had_error = False

    data = []

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
        await update.message.reply_text(
            'Произошла ошибка. Попробуйте еще раз позже.'
        )
        return None

    data = response.json().get('results', [])  # Парсим JSON ответ

    if not data:
        await update.message.reply_text(
            'Ничего не получилось найти.'
        )
        return None

    text = 'Выбери одну песню из найденных:'
    inline_keyboards = []
    for i, item in enumerate(data, start=1):
        id = item.get('id')
        title = item.get('title', 'Без названия')
        artists = ', '.join(item.get('artists', ['Неизвестный']))
        duration = item.get('duration')
        text += f'\n {i}) {title} – {artists} ({duration})'
        inline_keyboards.append(
            InlineKeyboardButton(
                str(i),
                callback_data=str(id))
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


async def save_audio_by_id(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет песню по id из callback query."""
    clear(update, context)

    assert update.callback_query is not None

    query = update.callback_query
    await query.answer()

    logger.info(query.data)

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
async def print_time_codes(update: Update,
                           context: ContextTypes.DEFAULT_TYPE) -> str:
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
        'Максимальная длина кружочка - 1 минута. '
        'Можем начать с начала или выбрать особый отрезок песни.',
        reply_markup=reply_markup
    )

    return st.SELECTING_ACTION


# SELECTING_ACTION
async def set_start_time(update: Update,
                         context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Устанавливает время по умолчанию - с начала.
    """
    assert update.callback_query is not None

    query = update.callback_query
    await query.answer()

    assert context.user_data is not None

    context.user_data[st.DURATION_LEFT_BORDER] = str(0)
    context.user_data[st.DURATION_RIGHT_BORDER] = str(
        min(60, int(context.user_data[st.FILE_DURATION])))

    keyboard = get_main_menu(context)

    await query.edit_message_text(
        '✅Будем отсчитывать сначала.\nВыберите опцию:',
        reply_markup=keyboard
    )

    return ConversationHandler.END


# SELECTING_ACTION
async def print_custom_time_text(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE) -> str:
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
async def set_custom_time(update: Update,
                          context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Принимает сообщение с указанием времени, запоминает его и возвращает меню.
    """
    assert update.message is not None
    assert update.message.text is not None

    text = update.message.text
    time_codes = tuple(map(get_seconds, text.split()))

    assert context.user_data is not None

    user_data = context.user_data

    user_data[st.DURATION_LEFT_BORDER] = str(
        time_codes[0])  # добавить обработчик значений

    if len(time_codes) == 2:
        user_data[st.DURATION_RIGHT_BORDER] = str(time_codes[1])
    else:
        user_data[st.DURATION_RIGHT_BORDER] = str(
            min(time_codes[0] + 60, int(user_data[st.FILE_DURATION])))

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
async def back_to_menu(update: Update,
                       context: ContextTypes.DEFAULT_TYPE) -> int:
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
async def create_video_message(update: Update,
                               context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Создает видео сообщение из ранее полученных данных.
    """
    assert update.callback_query is not None
    assert update.effective_chat is not None

    query = update.callback_query
    await query.answer()
    await query.edit_message_text('Хорошо, создаю кружок')

    bot = context.bot
    chat_id = update.effective_chat.id

    VIDEO_NOTE_PATH = 'your_path'

    if not os.path.exists(VIDEO_NOTE_PATH):
        logger.error(f'Файл видео не найден по пути: {VIDEO_NOTE_PATH}')
        await query.edit_message_text(
            'Ошибка, не могу создать кружок 😢'
        )
        return ConversationHandler.END

    try:
        logger.info(f'Попытка отправить видео-кружок в chat_id: {chat_id}')

        # Открываем файл в бинарном режиме для чтения ('rb')
        with open(VIDEO_NOTE_PATH, 'rb') as video_file:
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

    clear(update, context)
    return ConversationHandler.END


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Команда для остановки бота, вызов clear.
    """
    pass


def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    if user_data.get(st.MP3_FILE_PATH):
        path = user_data[st.MP3_FILE_PATH]
        if os.path.exists(path):
            os.remove(path)
            logger.info(f'{user_info}: File {path} has been deleted')
        else:
            logger.info(f'{user_info}: File {path} has already been deleted')

    user_data.clear()

    logger.info(f'{user_info}: user_data has been cleared')
