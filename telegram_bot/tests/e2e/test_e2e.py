import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from telegram.ext import ConversationHandler

import src.handlers as handlers
import src.states as st
from src.api_utils import TrackInfo


async def _mock_download_track_stream(track_id: str, save_dir: str) -> str:
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, f"{track_id}.mp3")
    with open(file_path, "wb") as file:
        file.write(b"audio")
    return file_path


async def _mock_trim_audio(
    file_path: str,
    start: int,
    end: int,
    output_path: str,
) -> bool:
    with open(output_path, "wb") as file:
        file.write(f"trim:{file_path}:{start}:{end}".encode("utf-8"))
    return True


async def _mock_download_cover(track_id: str, save_dir: str) -> str:
    file_path = os.path.join(save_dir, f"{track_id}.jpg")
    with open(file_path, "wb") as file:
        file.write(b"cover")
    return file_path


async def _mock_create_video(
    audio_path: str,
    image_path: str,
    output_path: str,
) -> bool:
    with open(output_path, "wb") as file:
        file.write(f"video:{audio_path}:{image_path}".encode("utf-8"))
    return True


def _extract_edited_text(edit_mock: AsyncMock) -> str:
    args, kwargs = edit_mock.call_args
    if "text" in kwargs:
        return kwargs["text"]
    if args:
        return args[0]
    return ""


@pytest.mark.asyncio
async def test_scenario_01_happy_path_default_settings(
    context_factory,
    message_update_factory,
    callback_update_factory,
):
    context = context_factory()

    start_update = message_update_factory(text="/start")
    await handlers.start(start_update, context)
    start_update.message.reply_text.assert_called_once()

    search_update = message_update_factory(
        text="Nirvana Smells Like Teen Spirit"
    )
    mock_log = AsyncMock(return_value=True)
    mock_search = AsyncMock(
        return_value=[
            TrackInfo(
                id=101,
                title="Smells Like Teen Spirit",
                artists="Nirvana",
                duration=301,
            )
        ]
    )

    with (
        patch("src.handlers.db_utils.log_interaction", mock_log),
        patch("src.handlers.api_utils.search_for_tracks", mock_search),
    ):
        search_state = await handlers.search_audio_by_name(search_update, context)

    assert search_state == st.SELECTING_SONG

    select_update = callback_update_factory(data="101")
    mock_track_info = AsyncMock(return_value=301)

    with patch("src.handlers.api_utils.get_track_info", mock_track_info):
        selection_state = await handlers.save_selected_audio(select_update, context)

    assert selection_state == ConversationHandler.END

    create_update = callback_update_factory(data=st.CREATE_VIDEO_MESSAGE)

    with tempfile.TemporaryDirectory() as temp_dir:
        mock_stream = AsyncMock(side_effect=_mock_download_track_stream)
        mock_trim = AsyncMock(side_effect=_mock_trim_audio)
        mock_cover = AsyncMock(side_effect=_mock_download_cover)
        mock_video = AsyncMock(side_effect=_mock_create_video)

        with (
            patch("src.handlers.conf.DOWNLOAD_FOLDER", temp_dir),
            patch("src.handlers.db_utils.log_interaction", AsyncMock(return_value=True)),
            patch("src.handlers.api_utils.download_track_stream", mock_stream),
            patch("src.handlers.api_utils.trim_audio", mock_trim),
            patch("src.handlers.api_utils.download_cover", mock_cover),
            patch("src.handlers.api_utils.create_video", mock_video),
        ):
            end_state = await handlers.create_video_message(create_update, context)

    assert end_state == ConversationHandler.END
    assert create_update.callback_query.edit_message_text.call_count >= 4
    context.bot.send_video_note.assert_called_once()

    trim_kwargs = mock_trim.await_args.kwargs
    assert trim_kwargs["start"] == 0
    assert trim_kwargs["end"] <= 55
    assert context.user_data == {}


@pytest.mark.asyncio
async def test_scenario_02_custom_timecode_mm_ss(
    context_factory,
    message_update_factory,
    callback_update_factory,
):
    context = context_factory()

    search_update = message_update_factory(text="Custom Time Song")
    with (
        patch("src.handlers.db_utils.log_interaction", AsyncMock(return_value=True)),
        patch(
            "src.handlers.api_utils.search_for_tracks",
            AsyncMock(return_value=[TrackInfo(202, "Track", "Artist", 260)]),
        ),
    ):
        search_state = await handlers.search_audio_by_name(search_update, context)

    assert search_state == st.SELECTING_SONG

    with patch("src.handlers.api_utils.get_track_info", AsyncMock(return_value=260)):
        selection_state = await handlers.save_selected_audio(
            callback_update_factory(data="202"),
            context,
        )
    assert selection_state == ConversationHandler.END

    action_state = await handlers.print_time_codes(
        callback_update_factory(data=st.SET_TIME_CODE),
        context,
    )
    assert action_state == st.SELECTING_ACTION

    input_state = await handlers.print_custom_time_text(
        callback_update_factory(data=st.DURATION_CUSTOM),
        context,
    )
    assert input_state == st.INPUT_TIME_CODE

    custom_input = message_update_factory(text="00:30 01:10")
    custom_state = await handlers.set_custom_time(custom_input, context)

    assert custom_state == ConversationHandler.END
    assert context.user_data[st.DURATION_LEFT_BORDER] == "30"
    assert context.user_data[st.DURATION_RIGHT_BORDER] == "70"

    with tempfile.TemporaryDirectory() as temp_dir:
        mock_trim = AsyncMock(side_effect=_mock_trim_audio)
        with (
            patch("src.handlers.conf.DOWNLOAD_FOLDER", temp_dir),
            patch("src.handlers.db_utils.log_interaction", AsyncMock(return_value=True)),
            patch(
                "src.handlers.api_utils.download_track_stream",
                AsyncMock(side_effect=_mock_download_track_stream),
            ),
            patch("src.handlers.api_utils.trim_audio", mock_trim),
            patch(
                "src.handlers.api_utils.download_cover",
                AsyncMock(side_effect=_mock_download_cover),
            ),
            patch(
                "src.handlers.api_utils.create_video",
                AsyncMock(side_effect=_mock_create_video),
            ),
        ):
            end_state = await handlers.create_video_message(
                callback_update_factory(data=st.CREATE_VIDEO_MESSAGE),
                context,
            )

    assert end_state == ConversationHandler.END
    trim_kwargs = mock_trim.await_args.kwargs
    assert trim_kwargs["start"] == 30
    assert trim_kwargs["end"] == 70
    context.bot.send_video_note.assert_called_once()


@pytest.mark.asyncio
async def test_scenario_03_empty_search_then_retry(
    context_factory,
    message_update_factory,
):
    context = context_factory()

    empty_update = message_update_factory(text="qwerty_nonexistent_track_12345")
    retry_update = message_update_factory(text="Nirvana")

    mock_search = AsyncMock(
        side_effect=[
            [],
            [TrackInfo(303, "Smells Like Teen Spirit", "Nirvana", 301)],
        ]
    )

    with (
        patch("src.handlers.db_utils.log_interaction", AsyncMock(return_value=True)),
        patch("src.handlers.api_utils.search_for_tracks", mock_search),
    ):
        first_state = await handlers.search_audio_by_name(empty_update, context)
        second_state = await handlers.search_audio_by_name(retry_update, context)

    assert first_state is None
    empty_update.message.reply_text.assert_called_once_with(
        "Ничего не получилось найти. Попробуйте написать еще раз."
    )

    assert second_state == st.SELECTING_SONG
    retry_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_scenario_04_search_service_temporary_unavailable_then_recovered(
    context_factory,
    message_update_factory,
):
    context = context_factory()

    failed_update = message_update_factory(text="Unavailable Song")
    recovered_update = message_update_factory(text="Recovered Song")

    mock_search = AsyncMock(
        side_effect=[
            None,
            [TrackInfo(404, "Recovered Song", "Recovered Artist", 280)],
        ]
    )

    with (
        patch("src.handlers.db_utils.log_interaction", AsyncMock(return_value=True)),
        patch("src.handlers.api_utils.search_for_tracks", mock_search),
    ):
        first_state = await handlers.search_audio_by_name(failed_update, context)
        second_state = await handlers.search_audio_by_name(recovered_update, context)

    assert first_state is None
    failed_update.message.reply_text.assert_called_once_with(
        "Произошла ошибка. Попробуйте еще раз позже."
    )

    assert second_state == st.SELECTING_SONG
    recovered_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_scenario_05_invalid_time_interval_validation_then_success(
    context_factory,
    message_update_factory,
    callback_update_factory,
):
    context = context_factory()

    with (
        patch("src.handlers.db_utils.log_interaction", AsyncMock(return_value=True)),
        patch(
            "src.handlers.api_utils.search_for_tracks",
            AsyncMock(return_value=[TrackInfo(505, "Song", "Artist", 300)]),
        ),
    ):
        await handlers.search_audio_by_name(
            message_update_factory(text="Validation Song"),
            context,
        )

    with patch("src.handlers.api_utils.get_track_info", AsyncMock(return_value=300)):
        await handlers.save_selected_audio(callback_update_factory(data="505"), context)

    await handlers.print_time_codes(callback_update_factory(data=st.SET_TIME_CODE), context)
    await handlers.print_custom_time_text(
        callback_update_factory(data=st.DURATION_CUSTOM),
        context,
    )

    invalid_input = message_update_factory(text="01:00 00:30")
    invalid_state = await handlers.set_custom_time(invalid_input, context)

    assert invalid_state == st.INPUT_TIME_CODE
    invalid_input.message.reply_text.assert_called_once()
    invalid_reply = invalid_input.message.reply_text.call_args.args[0]
    assert "ошиб" in invalid_reply.lower()

    valid_input = message_update_factory(text="00:10 00:50")
    valid_state = await handlers.set_custom_time(valid_input, context)

    assert valid_state == ConversationHandler.END
    assert context.user_data[st.DURATION_LEFT_BORDER] == "10"
    assert context.user_data[st.DURATION_RIGHT_BORDER] == "50"


@pytest.mark.asyncio
async def test_scenario_06_cover_unavailable_uses_default_image(
    context_factory,
    callback_update_factory,
):
    context = context_factory()
    context.user_data = {
        st.TRACK_ID: "606",
        st.DURATION_LEFT_BORDER: "0",
        st.DURATION_RIGHT_BORDER: "40",
        st.FILE_DURATION: "180",
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        mock_create_video = AsyncMock(side_effect=_mock_create_video)
        with (
            patch("src.handlers.conf.DOWNLOAD_FOLDER", temp_dir),
            patch("src.handlers.db_utils.log_interaction", AsyncMock(return_value=True)),
            patch(
                "src.handlers.api_utils.download_track_stream",
                AsyncMock(side_effect=_mock_download_track_stream),
            ),
            patch("src.handlers.api_utils.trim_audio", AsyncMock(side_effect=_mock_trim_audio)),
            patch("src.handlers.api_utils.download_cover", AsyncMock(return_value="")),
            patch("src.handlers.api_utils.create_video", mock_create_video),
        ):
            end_state = await handlers.create_video_message(
                callback_update_factory(data=st.CREATE_VIDEO_MESSAGE),
                context,
            )

    assert end_state == ConversationHandler.END
    assert mock_create_video.await_args.kwargs["image_path"] == "video_note_images/vinyl_default.jpg"
    context.bot.send_video_note.assert_called_once()


@pytest.mark.asyncio
async def test_scenario_07_media_processing_error_shows_clear_failure(
    context_factory,
    callback_update_factory,
):
    context = context_factory()
    context.user_data = {
        st.TRACK_ID: "707",
        st.DURATION_LEFT_BORDER: "0",
        st.DURATION_RIGHT_BORDER: "40",
        st.FILE_DURATION: "180",
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        with (
            patch("src.handlers.conf.DOWNLOAD_FOLDER", temp_dir),
            patch("src.handlers.db_utils.log_interaction", AsyncMock(return_value=True)),
            patch(
                "src.handlers.api_utils.download_track_stream",
                AsyncMock(side_effect=_mock_download_track_stream),
            ),
            patch("src.handlers.api_utils.trim_audio", AsyncMock(return_value=False)),
            patch("src.handlers.api_utils.download_cover", AsyncMock(side_effect=_mock_download_cover)),
            patch("src.handlers.api_utils.create_video", AsyncMock(side_effect=_mock_create_video)),
        ):
            update = callback_update_factory(data=st.CREATE_VIDEO_MESSAGE)
            end_state = await handlers.create_video_message(update, context)

    assert end_state == ConversationHandler.END
    assert update.callback_query.edit_message_text.call_count >= 2
    assert "Ошибка, при создании кружка" in _extract_edited_text(update.callback_query.edit_message_text)
    context.bot.send_video_note.assert_not_called()


@pytest.mark.asyncio
async def test_scenario_08_database_logging_down_does_not_block_user_flow(
    context_factory,
    message_update_factory,
    callback_update_factory,
):
    context = context_factory()

    mock_log = AsyncMock(return_value=False)
    with (
        patch("src.handlers.db_utils.log_interaction", mock_log),
        patch(
            "src.handlers.api_utils.search_for_tracks",
            AsyncMock(return_value=[TrackInfo(808, "Song", "Artist", 300)]),
        ),
    ):
        search_state = await handlers.search_audio_by_name(
            message_update_factory(text="Logging Down Song"),
            context,
        )

    assert search_state == st.SELECTING_SONG

    with patch("src.handlers.api_utils.get_track_info", AsyncMock(return_value=300)):
        selection_state = await handlers.save_selected_audio(
            callback_update_factory(data="808"),
            context,
        )

    assert selection_state == ConversationHandler.END

    with tempfile.TemporaryDirectory() as temp_dir:
        with (
            patch("src.handlers.conf.DOWNLOAD_FOLDER", temp_dir),
            patch("src.handlers.db_utils.log_interaction", mock_log),
            patch(
                "src.handlers.api_utils.download_track_stream",
                AsyncMock(side_effect=_mock_download_track_stream),
            ),
            patch("src.handlers.api_utils.trim_audio", AsyncMock(side_effect=_mock_trim_audio)),
            patch("src.handlers.api_utils.download_cover", AsyncMock(side_effect=_mock_download_cover)),
            patch("src.handlers.api_utils.create_video", AsyncMock(side_effect=_mock_create_video)),
        ):
            end_state = await handlers.create_video_message(
                callback_update_factory(data=st.CREATE_VIDEO_MESSAGE),
                context,
            )

    assert end_state == ConversationHandler.END
    assert mock_log.await_count == 2
    context.bot.send_video_note.assert_called_once()


@pytest.mark.asyncio
async def test_scenario_09_parallel_users_sessions_are_isolated(
    context_factory,
    message_update_factory,
    callback_update_factory,
):
    users = [
        {"user_id": 1001, "chat_id": 9001, "start": 1, "end": 21},
        {"user_id": 1002, "chat_id": 9002, "start": 2, "end": 22},
        {"user_id": 1003, "chat_id": 9003, "start": 3, "end": 23},
        {"user_id": 1004, "chat_id": 9004, "start": 4, "end": 24},
        {"user_id": 1005, "chat_id": 9005, "start": 5, "end": 25},
    ]

    async def mock_search(track_name: str):
        user_id = int(track_name.split("_")[-1])
        track_id = user_id + 5000
        return [TrackInfo(track_id, f"Song {user_id}", f"Artist {user_id}", 320)]

    async def mock_track_info(track_id: str):
        return 320

    with tempfile.TemporaryDirectory() as temp_dir:
        mock_trim = AsyncMock(side_effect=_mock_trim_audio)

        async def run_flow(user_case):
            user_id = user_case["user_id"]
            chat_id = user_case["chat_id"]
            start_value = user_case["start"]
            end_value = user_case["end"]
            track_id = user_id + 5000

            context = context_factory()

            await handlers.start(
                message_update_factory(
                    text="/start",
                    user_id=user_id,
                    username=f"u{user_id}",
                    chat_id=chat_id,
                ),
                context,
            )

            search_state = await handlers.search_audio_by_name(
                message_update_factory(
                    text=f"parallel_{user_id}",
                    user_id=user_id,
                    username=f"u{user_id}",
                    chat_id=chat_id,
                ),
                context,
            )
            assert search_state == st.SELECTING_SONG

            selection_state = await handlers.save_selected_audio(
                callback_update_factory(
                    data=str(track_id),
                    user_id=user_id,
                    username=f"u{user_id}",
                    chat_id=chat_id,
                ),
                context,
            )
            assert selection_state == ConversationHandler.END

            await handlers.print_time_codes(
                callback_update_factory(
                    data=st.SET_TIME_CODE,
                    user_id=user_id,
                    username=f"u{user_id}",
                    chat_id=chat_id,
                ),
                context,
            )

            await handlers.print_custom_time_text(
                callback_update_factory(
                    data=st.DURATION_CUSTOM,
                    user_id=user_id,
                    username=f"u{user_id}",
                    chat_id=chat_id,
                ),
                context,
            )

            custom_state = await handlers.set_custom_time(
                message_update_factory(
                    text=f"00:{start_value:02d} 00:{end_value:02d}",
                    user_id=user_id,
                    username=f"u{user_id}",
                    chat_id=chat_id,
                ),
                context,
            )
            assert custom_state == ConversationHandler.END

            create_state = await handlers.create_video_message(
                callback_update_factory(
                    data=st.CREATE_VIDEO_MESSAGE,
                    user_id=user_id,
                    username=f"u{user_id}",
                    chat_id=chat_id,
                ),
                context,
            )
            assert create_state == ConversationHandler.END
            return context, user_case, track_id

        with (
            patch("src.handlers.conf.DOWNLOAD_FOLDER", temp_dir),
            patch("src.handlers.db_utils.log_interaction", AsyncMock(return_value=True)),
            patch("src.handlers.api_utils.search_for_tracks", AsyncMock(side_effect=mock_search)),
            patch("src.handlers.api_utils.get_track_info", AsyncMock(side_effect=mock_track_info)),
            patch(
                "src.handlers.api_utils.download_track_stream",
                AsyncMock(side_effect=_mock_download_track_stream),
            ),
            patch("src.handlers.api_utils.trim_audio", mock_trim),
            patch("src.handlers.api_utils.download_cover", AsyncMock(side_effect=_mock_download_cover)),
            patch("src.handlers.api_utils.create_video", AsyncMock(side_effect=_mock_create_video)),
        ):
            results = await asyncio.gather(*[run_flow(user_case) for user_case in users])

    assert len(results) == 5

    for context, user_case, _ in results:
        context.bot.send_video_note.assert_called_once()
        send_kwargs = context.bot.send_video_note.call_args.kwargs
        assert send_kwargs["chat_id"] == user_case["chat_id"]

    actual_calls = {
        (
            call.kwargs["start"],
            call.kwargs["end"],
            call.kwargs["output_path"].split("trimmed_")[1].replace(".mp3", ""),
        )
        for call in mock_trim.await_args_list
    }
    expected_calls = {
        (user_case["start"], user_case["end"], str(user_case["user_id"] + 5000))
        for user_case in users
    }
    assert expected_calls == actual_calls


@pytest.mark.asyncio
async def test_scenario_10_second_full_cycle_without_restart(
    context_factory,
    message_update_factory,
    callback_update_factory,
):
    context = context_factory()

    async def mock_search(track_name: str):
        if track_name == "first cycle":
            return [TrackInfo(10001, "First", "Artist A", 280)]
        return [TrackInfo(10002, "Second", "Artist B", 280)]

    async def run_cycle(track_name: str, track_id: str, time_code: str):
        search_state = await handlers.search_audio_by_name(
            message_update_factory(text=track_name),
            context,
        )
        assert search_state == st.SELECTING_SONG

        selection_state = await handlers.save_selected_audio(
            callback_update_factory(data=track_id),
            context,
        )
        assert selection_state == ConversationHandler.END

        await handlers.print_time_codes(
            callback_update_factory(data=st.SET_TIME_CODE),
            context,
        )
        await handlers.print_custom_time_text(
            callback_update_factory(data=st.DURATION_CUSTOM),
            context,
        )

        custom_state = await handlers.set_custom_time(
            message_update_factory(text=time_code),
            context,
        )
        assert custom_state == ConversationHandler.END

        create_state = await handlers.create_video_message(
            callback_update_factory(data=st.CREATE_VIDEO_MESSAGE),
            context,
        )
        assert create_state == ConversationHandler.END

    with tempfile.TemporaryDirectory() as temp_dir:
        mock_trim = AsyncMock(side_effect=_mock_trim_audio)

        with (
            patch("src.handlers.conf.DOWNLOAD_FOLDER", temp_dir),
            patch("src.handlers.db_utils.log_interaction", AsyncMock(return_value=True)),
            patch("src.handlers.api_utils.search_for_tracks", AsyncMock(side_effect=mock_search)),
            patch(
                "src.handlers.api_utils.get_track_info",
                AsyncMock(side_effect=[280, 280]),
            ),
            patch(
                "src.handlers.api_utils.download_track_stream",
                AsyncMock(side_effect=_mock_download_track_stream),
            ),
            patch("src.handlers.api_utils.trim_audio", mock_trim),
            patch("src.handlers.api_utils.download_cover", AsyncMock(side_effect=_mock_download_cover)),
            patch("src.handlers.api_utils.create_video", AsyncMock(side_effect=_mock_create_video)),
        ):
            await run_cycle("first cycle", "10001", "00:05 00:35")

            restart_state = await handlers.restart_conversation(
                callback_update_factory(data=st.RESTART_SEARCH),
                context,
            )
            assert restart_state == st.TYPING_SONG_NAME

            await run_cycle("second cycle", "10002", "00:40 01:10")

    assert context.bot.send_video_note.call_count == 2

    first_trim = mock_trim.await_args_list[0].kwargs
    second_trim = mock_trim.await_args_list[1].kwargs

    assert (first_trim["start"], first_trim["end"]) == (5, 35)
    assert (second_trim["start"], second_trim["end"]) == (40, 70)
