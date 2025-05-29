import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import src.states as st

from src.config import TB_TOKEN
import src.handlers as hnd


# Enable logging
logging.basicConfig(
    format=(
        '%(asctime)s - %(name)s - '
        '%(levelname)s - %(funcName)s - %(message)s'
    ),
    level=logging.INFO
)
# set higher logging level for httpx
# to avoid all GET and POST requests being logged
logging.getLogger('httpx').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def main() -> None:
    assert TB_TOKEN is not None

    application = Application.builder().token(TB_TOKEN).build()

    start_handler = CommandHandler('start', hnd.start)

    selecting_song_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.TEXT,
                hnd.search_audio_by_name
            )
        ],
        states={
            st.SELECTING_SONG: [
                CallbackQueryHandler(
                    hnd.save_selected_audio,
                    pattern=r'^\d+$'
                )
            ],
            st.TYPING_SONG_NAME: [
                MessageHandler(
                    filters.TEXT,
                    hnd.search_audio_by_name
                )
            ]
        },
        fallbacks=[],
        map_to_parent={
            ConversationHandler.END: st.CHOOSING_OPTIONS,
        }
    )

    time_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                hnd.print_time_codes,
                pattern='^' + str(st.SET_TIME_CODE) + '$'
            )
        ],
        states={
            st.SELECTING_ACTION: [
                # После выполнения ConversationHandler.END.
                CallbackQueryHandler(
                    hnd.set_start_time,
                    pattern='^' + str(st.DURATION_START) + '$'
                ),

                # После выполнения INPUT_TIME_CODE.
                CallbackQueryHandler(
                    hnd.print_custom_time_text,
                    pattern='^' + str(st.DURATION_CUSTOM) + '$'
                ),

                # После выполнения ConversationHandler.END.
                CallbackQueryHandler(
                    hnd.back_to_menu,
                    pattern='^' + str(st.BACK_TO_MENU) + '$'
                ),
            ],
            st.INPUT_TIME_CODE: [
                # После выполнения ConversationHandler.END.
                MessageHandler(
                    filters.Regex(
                        r'^(\d{1,2}:\d{1,2}( \d{1,2}:\d{1,2})?|'
                        r'\d{1,2}( \d{1,2})?)$'
                    ),
                    hnd.set_custom_time
                ),
            ],
        },
        fallbacks=[],
        map_to_parent={
            ConversationHandler.END: st.CHOOSING_OPTIONS,
        }
    )

    # cover_conv_handler = ConversationHandler(
    #     entry_points=[

    #     ],
    #     states={

    #     },
    #     fallbacks=[],
    # )

    main_conv_handler = ConversationHandler(
        # Принимает аудио или название песни и выводит кнопки для выбора опций.
        entry_points=[
            # Handler для обработки присланных аудиофайлов/голосовых.
            # MessageHandler(
            #     filters.AUDIO | filters.VOICE,
            #     hnd.save_audio
            # ),

            # Handler для обработки поиска аудиофайлов.
            selecting_song_conv_handler
        ],
        states={
            st.CHOOSING_OPTIONS: [
                # Handler, который обрабатывает с отрезок аудио.
                time_conv_handler,

                # Handler, который начинает создавать кружок.
                CallbackQueryHandler(
                    hnd.create_video_message,
                    pattern='^' + str(st.CREATE_VIDEO_MESSAGE) + '$'
                ),
            ],
        },
        # Пустышка, необходимо сделать так,
        # что бы метод оставнавливал работу и чистил память.
        fallbacks=[
            MessageHandler(
                filters.Regex('^Done$'),
                hnd.done
            )
        ],
    )

    application.add_handler(start_handler)
    application.add_handler(main_conv_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
