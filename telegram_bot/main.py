from dotenv import load_dotenv  # type: ignore
import os
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Загрузка переменных окружения
load_dotenv()

TB_TOKEN = os.getenv("TB_TOKEN")
DOWNLOAD_FOLDER = os.getenv("DOWNLOAD_FOLDER")


# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
# set higher logging level for httpx
# to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Константы для работы бота
(
    CHOOSING_OPTIONS, SELECTING_ACTION, INPUT_TIME_CODE,    # states
    MP3_FILE_PATH, FILE_DURATION, DURATION_LEFT_BORDER,     # user_data
    DURATION_RIGHT_BORDER,
    DURATION_START, DURATION_CUSTOM, SET_TIME_CODE,         # callback_queries
    BACK_TO_MENU, CREATE_VIDEO_MESSAGE
) = map(chr, range(12))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Печатает приветственное сообщение.
    """
    assert update.message is not None
    assert update.message.from_user is not None

    user = update.message.from_user
    logger.info(f"{user.id} started bot")

    await update.message.reply_text(
        "Привет, я бот, который создает музыкальные кружочки.\n"
        "Пришли мне файл с твоей песней или голосовое сообщение"
    )


def get_main_menu(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    """
    Возвращает основное меню.

    :param context: Контекст для получения уже установленных настроек.

    :return: Разметка клавиатуры, являющейся меню.
    """
    assert context.user_data is not None

    user_data = context.user_data

    time_code_message = ("⏱️Редактировать время: с "
                         f"{user_data[DURATION_LEFT_BORDER]}с "
                         f"по {user_data[DURATION_RIGHT_BORDER]}с")

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    time_code_message,
                    callback_data=SET_TIME_CODE),
            ],
            [
                InlineKeyboardButton(
                    "▶️Создать кружок",
                    callback_data=CREATE_VIDEO_MESSAGE),
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
        await message.reply_text("Отправьте аудиофайл (MP3, OGG, WAV).")
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
            f"Файл слишком большой: {file_size / 1024 / 1024:.2f} MB! "
            "Максимальный размер – 6MB."
        )
        return None

    # Проверяем допустимые MIME-типы
    allowed_mime = {"audio/mpeg", "audio/ogg", "audio/wav"}
    if mime_type not in allowed_mime:
        await message.reply_text(
            "Неподдерживаемый формат! Используйте MP3, OGG, WAV."
        )
        return None

    assert context.user_data is not None

    user_data = context.user_data

    file_duration = audio.duration
    user_data[FILE_DURATION] = str(file_duration)

    file_name_extension = get_file_name_extension(mime_type)
    file_name = file_id + file_name_extension

    # Скачиваем файл
    file = await context.bot.get_file(file_id)

    assert DOWNLOAD_FOLDER is not None

    file_path = os.path.join(DOWNLOAD_FOLDER, f"{file_name}")
    user_data[MP3_FILE_PATH] = file_path
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

    await file.download_to_drive(file_path)

    logger.info(f"Файл сохранён: Размер - {file_size} Путь - {file_path}")

    await message.reply_text("Файл загружен!")

    # настройки по умолчанию, после вынести в отдельный метод
    user_data[DURATION_LEFT_BORDER] = str(0)
    user_data[DURATION_RIGHT_BORDER] = str(min(60, file_duration))

    keyboard = get_main_menu(context)

    await message.reply_text("Выберите опцию:", reply_markup=keyboard)

    return CHOOSING_OPTIONS


def get_file_name_extension(mime: str) -> str:
    """
    Возвращает тип файла исходя из MIME-типов.

    :param mime: MIME-тип.

    :return: Расширение имени файла.
    """
    match mime:
        case "audio/mpeg":
            return ".mp3"
        case "audio/ogg":
            return ".ogg"
        case "audio/x-wav":
            return ".wav"
        case _:
            return ""


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
            InlineKeyboardButton("⭐️С начала", callback_data=DURATION_START),
            InlineKeyboardButton("Ввести время самому",
                                 callback_data=DURATION_CUSTOM),
        ],
        [
            InlineKeyboardButton("Назад", callback_data=BACK_TO_MENU),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    assert context.user_data is not None

    audio_duration = context.user_data[FILE_DURATION]

    await query.edit_message_text(
        f"Теперь давай обрежем твой аудиофайл как надо!\n"
        f"Его длительность {audio_duration}с. "
        "Максимальная длина кружочка - 1 минута. "
        "Можем начать с начала или выбрать особый отрезок песни.",
        reply_markup=reply_markup
    )

    return SELECTING_ACTION


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

    context.user_data[DURATION_LEFT_BORDER] = str(0)
    context.user_data[DURATION_RIGHT_BORDER] = str(
        min(60, int(context.user_data[FILE_DURATION])))

    keyboard = get_main_menu(context)

    await query.edit_message_text(
        "✅Будем отсчитывать сначала.\nВыберите опцию:",
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
        "Хорошо, задай время или в формате мм:сс или сс для "
        "обозначения начала, или мм:сс мм:сс или сс сс для "
        "обозначения интервалов (через пробел)."
    )

    return INPUT_TIME_CODE


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

    user_data[DURATION_LEFT_BORDER] = str(
        time_codes[0])  # добавить обработчик значений

    if len(time_codes) == 2:
        user_data[DURATION_RIGHT_BORDER] = str(time_codes[1])
    else:
        user_data[DURATION_RIGHT_BORDER] = str(
            min(time_codes[0] + 60, int(user_data[FILE_DURATION])))

    keyboard = get_main_menu(context)

    await update.message.reply_text(
        f"✅Возьмем аудио с {context.user_data[DURATION_LEFT_BORDER]}с по "
        f"{context.user_data[DURATION_RIGHT_BORDER]}с.\nВыберите опцию:",
        reply_markup=keyboard
    )

    return ConversationHandler.END


def get_seconds(time: str) -> int:
    """
    Получение секунд из строки, являющейся временем.

    :param time: Время в виде mm:ss или ss.

    :return: Время в секундах.
    """
    if ":" in time:
        m, s = map(int, time.split(":"))
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
        "Выберите опцию:",
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

    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Хорошо, создаю кружок")

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

        user_info = (f"{update.message.from_user.id} - "
                     f"{update.message.from_user.username}")
    else:
        assert update.callback_query is not None

        user_info = (f"{update.callback_query.from_user.id} - "
                     f"{update.callback_query.from_user.username}")

    assert context.user_data is not None

    user_data = context.user_data

    if user_data.get(MP3_FILE_PATH):
        path = user_data[MP3_FILE_PATH]
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"{user_info}: File {path} has been deleted")
        else:
            logger.info(f"{user_info}: File {path} has already been deleted")

    user_data.clear()

    logger.info(f"{user_info}: user_data has been cleared")


def main() -> None:
    assert TB_TOKEN is not None

    application = Application.builder().token(TB_TOKEN).build()

    start_handler = CommandHandler("start", start)

    time_conv_handler = ConversationHandler(
        # Функция должна редактировать сообщение:
        # клавиатура с выбором времени с начала, кастом и "назад"
        # return.
        entry_points=[CallbackQueryHandler(
            print_time_codes, pattern="^" + str(SET_TIME_CODE) + "$")],
        states={
            SELECTING_ACTION: [
                # После выполнения ConversationHandler.END.
                CallbackQueryHandler(
                    set_start_time, pattern="^" + str(DURATION_START) + "$"),
                # После выполнения INPUT_TIME_CODE.
                CallbackQueryHandler(print_custom_time_text,
                                     pattern="^" + str(DURATION_CUSTOM) + "$"),
                # После выполнения ConversationHandler.END.
                CallbackQueryHandler(
                    back_to_menu, pattern="^" + str(BACK_TO_MENU) + "$"),
            ],
            INPUT_TIME_CODE: [
                # После выполнения ConversationHandler.END.
                MessageHandler(
                    filters.Regex(
                        r"^(\d{1,2}:\d{1,2}( \d{1,2}:\d{1,2})?|"
                        r"\d{1,2}( \d{1,2})?)$"
                    ),
                    set_custom_time),
            ],
        },
        fallbacks=[],
        map_to_parent={
            ConversationHandler.END: CHOOSING_OPTIONS,
        }
    )

    conv_handler = ConversationHandler(
        # Принимает аудио и выводит кнопки для выбора опций.
        entry_points=[MessageHandler(
            filters.AUDIO | filters.VOICE, save_audio)],
        states={
            CHOOSING_OPTIONS: [
                # Handler, который обрабатывает с отрезок аудио.
                time_conv_handler,
                # Handler, который начинает создавать кружок.
                CallbackQueryHandler(
                    create_video_message,
                    pattern="^" + str(CREATE_VIDEO_MESSAGE) + "$"
                ),
            ],
        },
        # Пустышка, необходимо сделать так,
        # что бы метод оставнавливал работу и чистил память.
        fallbacks=[MessageHandler(filters.Regex("^Done$"), done)],
    )

    application.add_handler(start_handler)
    application.add_handler(conv_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
