from dotenv import load_dotenv
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

load_dotenv("config/config.env")

TB_TOKEN = os.getenv("TB_TOKEN")
DOWNLOAD_FOLDER = os.getenv("DOWNLOAD_FOLDER")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

START, WAITING_FOR_AUDIO, PRINTING_TIME_CODE_TEXT, WAITING_FOR_TIME_CODE_OPTION, WAITING_FOR_CUSTOM_TIME_CODE, OUTPUT, \
    MP3_FILE_PATH, FILE_DURATION, \
    DURATION_START, DURATION_CUSTOM, DURATION_LEFT_BORDER, DURATION_RIGHT_BORDER = map(chr, range(12))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    user = update.message.from_user
    logger.info(f"{user.id} started bot")

    await update.message.reply_text(
        "Привет, я бот, который создает музыкальные кружочки.\n"
        "Пришли мне файл с твоей песней или голосовое сообщение"
    )

    return WAITING_FOR_AUDIO


def get_file_name_extension(mime: str) -> str:
    match mime:
        case "audio/mpeg":
            return ".mp3"
        case "audio/ogg":
            return ".ogg"
        case "audio/x-wav":
            return ".wav"


async def save_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Проверка аудио и запоминание file_id."""
    message = update.message

    # Проверяем, что пришел именно аудиофайл
    audio = message.audio or message.voice
    if not audio:
        await message.reply_text("Отправьте аудиофайл (MP3, OGG, WAV).")
        return
    print(audio)
    # Получаем информацию о файле
    file_id = audio.file_id
    file_size = audio.file_size  # Размер в байтах
    mime_type = audio.mime_type  # MIME-тип, например 'audio/mpeg' для mp3 и 'audio/ogg' для голосовых
    # file_name = getattr(audio, "file_name", "audio_file")  # Имя файла (если есть)

    # Ограничения по размеру (например, 6MB)
    max_file_size = 6 * 1024 * 1024  # 6 MB
    if file_size > max_file_size:
        await message.reply_text(f"Файл слишком большой: {file_size / 1024 / 1024:.2f} MB! Максимальный размер – 6MB.")
        return

    # Проверяем допустимые MIME-типы
    allowed_mime = {"audio/mpeg", "audio/ogg", "audio/wav"}
    if mime_type not in allowed_mime:
        await message.reply_text("Неподдерживаемый формат! Используйте MP3, OGG, WAV.")
        return

    context.user_data[FILE_DURATION] = audio.duration

    file_name_extension = get_file_name_extension(mime_type)
    file_name = file_id + file_name_extension

    # Скачиваем файл
    file = await context.bot.get_file(file_id)

    file_path = os.path.join(DOWNLOAD_FOLDER, f"{file_name}")  # Сохраняем как MP3
    print(file_path)
    context.user_data[MP3_FILE_PATH] = file_path
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

    await file.download_to_drive(file_path)

    logger.info(f"Файл сохранён: {file_path}")

    # Читаем и обрезаем аудиофайл (например, первые 10 секунд)
    # trimmed_path = file_path.replace(".mp3", "_trimmed.mp3")
    # audio_segment = AudioSegment.from_file(file_path)
    # trimmed_audio = audio_segment[:10_000]  # 10 секунд (в миллисекундах)
    # trimmed_audio.export(trimmed_path, format="mp3")
    #
    # logger.info(f"Обрезанный файл сохранён: {trimmed_path}")
    await message.reply_text("Файл загружен!")
    print(context.user_data[MP3_FILE_PATH], type(context.user_data[MP3_FILE_PATH]))
    print(context.user_data[FILE_DURATION], type(context.user_data[FILE_DURATION]))

    await print_time_codes(update, context)

    return WAITING_FOR_TIME_CODE_OPTION


async def print_time_codes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [
            InlineKeyboardButton("⭐️С начала", callback_data=DURATION_START),
            InlineKeyboardButton("Ввести время самому", callback_data=DURATION_CUSTOM),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    audio_duration = context.user_data[FILE_DURATION]
    await update.message.reply_text(f"Теперь давай обрежем твой аудиофайл как надо!\n"
                                    f"Его длительность {audio_duration}. "
                                    "Максимальная длина кружочка - 1 минута. "
                                    "Можем начать с начала или выбрать особый отрезок песни.",
                                    reply_markup=reply_markup)


# WAITING_FOR_TIME_CODE_OPTION
async def set_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅Будем отсчитывать сначала")

    context.user_data[DURATION_LEFT_BORDER] = str(0)
    context.user_data[DURATION_RIGHT_BORDER] = str(min(60, int(context.user_data[FILE_DURATION])))

    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    await trim_audio(update, context)
    await show_data(update, context)
    return ConversationHandler.END


# WAITING_FOR_TIME_CODE_OPTION
async def print_custom_time_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Хорошо, задай время или в формате мм:сс или сс для обозначения начала, "
        "или мм:сс мм:сс или сс сс для обозначения интервалов (через пробел)."
    )

    return WAITING_FOR_CUSTOM_TIME_CODE


# WAITING_FOR_CUSTOM_TIME_CODE
async def set_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    time_codes = tuple(map(get_seconds, text.split()))

    context.user_data[DURATION_LEFT_BORDER] = str(time_codes[0])    # добавить обработчик значений

    if len(time_codes) == 2:
        context.user_data[DURATION_RIGHT_BORDER] = str(time_codes[1])
    else:
        context.user_data[DURATION_RIGHT_BORDER] = str(time_codes[0] + 60)

    await update.message.reply_text(
        f"✅Возьмем аудио с {context.user_data[DURATION_LEFT_BORDER]}с по {context.user_data[DURATION_RIGHT_BORDER]}с."
    )
    await trim_audio(update, context)
    await show_data(update, context)
    return ConversationHandler.END


def get_seconds(time: str) -> int:
    if ":" in time:
        m, s = map(int, time.split(":"))
        return m * 60 + s
    return int(time)


async def trim_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = context.user_data
    await update.message.reply_text(
        f"⚙️Обрезаю аудио с {user_data[DURATION_LEFT_BORDER]}с по {user_data[DURATION_RIGHT_BORDER]}с."
    )


async def show_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Вывод информации")

    return ConversationHandler.END


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display the gathered info and end the conversation."""
    user_data = context.user_data

    await update.message.reply_text(
        f"fallbacks",
    )

    user_data.clear()
    return ConversationHandler.END


def main() -> None:
    application = Application.builder().token(TB_TOKEN).build()

    # audio_handler = MessageHandler(filters.AUDIO | filters.VOICE, save_audio)
    # time_code_handler = MessageHandler(filters.Regex(
    #     "^(\d{1,2}:\d{1,2}( \d{1,2}:\d{1,2})?|\d{1,2}( \d{1,2})?)$"), trim_audio)

    # application.add_handler(audio_handler)
    # application.add_handler(time_code_handler)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_FOR_AUDIO: [
                MessageHandler(filters.AUDIO | filters.VOICE, save_audio),
            ],
            WAITING_FOR_TIME_CODE_OPTION: [
                CallbackQueryHandler(set_start_time, pattern="^" + str(DURATION_START) + "$"),
                CallbackQueryHandler(print_custom_time_text, pattern="^" + str(DURATION_CUSTOM) + "$"),
            ],
            WAITING_FOR_CUSTOM_TIME_CODE: [
                MessageHandler(filters.TEXT, set_custom_time),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^Done$"), done)],
    )

    application.add_handler(conv_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
