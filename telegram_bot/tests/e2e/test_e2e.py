import asyncio
import uuid
from typing import Any, Sequence
from unittest.mock import AsyncMock, patch

import pytest
from telegram.ext import ConversationHandler

import src.handlers as handlers
import src.states as st


REAL_TRACK_QUERY = "Виктор Цой - Ночь"
ALT_TRACK_QUERIES = [
    "Кино - Группа крови",
    "Nirvana Smells Like Teen Spirit",
    "Imagine Dragons Believer",
]


def _extract_edited_text(edit_mock: AsyncMock) -> str:
    args, kwargs = edit_mock.call_args
    if "text" in kwargs:
        return kwargs["text"]
    if args:
        return args[0]
    return ""


def _extract_first_track_id(reply_mock: AsyncMock) -> str:
    _, kwargs = reply_mock.call_args
    reply_markup = kwargs.get("reply_markup")
    assert reply_markup is not None

    for row in reply_markup.inline_keyboard:
        for button in row:
            callback_data = getattr(button, "callback_data", None)
            if callback_data:
                return str(callback_data)

    raise AssertionError("No callback_data found in search reply keyboard")


async def _search_and_select(
    *,
    query: str,
    context: Any,
    message_update_factory: Any,
    callback_update_factory: Any,
    user_id: int = 123,
    username: str = "test_user",
    chat_id: int = 456,
) -> str:
    search_update = message_update_factory(
        text=query,
        user_id=user_id,
        username=username,
        chat_id=chat_id,
    )

    search_state = await handlers.search_audio_by_name(search_update, context)
    assert search_state == st.SELECTING_SONG

    track_id = _extract_first_track_id(search_update.message.reply_text)

    selection_update = callback_update_factory(
        data=track_id,
        user_id=user_id,
        username=username,
        chat_id=chat_id,
    )
    selection_state = await handlers.save_selected_audio(
        selection_update,
        context,
    )
    assert selection_state == ConversationHandler.END

    return track_id


async def _search_and_select_with_fallback(
    *,
    queries: Sequence[str],
    context: Any,
    message_update_factory: Any,
    callback_update_factory: Any,
    user_id: int = 123,
    username: str = "test_user",
    chat_id: int = 456,
) -> tuple[str, str]:
    errors: list[str] = []

    for query in queries:
        update = message_update_factory(
            text=query,
            user_id=user_id,
            username=username,
            chat_id=chat_id,
        )
        state = await handlers.search_audio_by_name(update, context)

        if state == st.SELECTING_SONG:
            track_id = _extract_first_track_id(update.message.reply_text)
            selection_update = callback_update_factory(
                data=track_id,
                user_id=user_id,
                username=username,
                chat_id=chat_id,
            )
            selection_state = await handlers.save_selected_audio(
                selection_update,
                context,
            )
            assert selection_state == ConversationHandler.END
            return track_id, query

        reply_text = update.message.reply_text.call_args.args[0]
        errors.append(f"{query}: {reply_text}")

    raise AssertionError(
        "Could not find selectable tracks for any query. "
        f"Attempts: {errors}"
    )


@pytest.mark.asyncio
async def test_e2e_scenario_01_default_happy_path(
    context_factory,
    message_update_factory,
    callback_update_factory,
):
    context = context_factory()

    start_update = message_update_factory(text="/start")
    await handlers.start(start_update, context)
    start_update.message.reply_text.assert_called_once()

    await _search_and_select(
        query=REAL_TRACK_QUERY,
        context=context,
        message_update_factory=message_update_factory,
        callback_update_factory=callback_update_factory,
    )

    trim_calls: list[dict[str, Any]] = []
    real_trim_audio = handlers.api_utils.trim_audio

    async def trim_spy(*args, **kwargs):
        trim_calls.append(kwargs.copy())
        return await real_trim_audio(*args, **kwargs)

    with patch("src.handlers.api_utils.trim_audio", side_effect=trim_spy):
        end_state = await handlers.create_video_message(
            callback_update_factory(data=st.CREATE_VIDEO_MESSAGE),
            context,
        )

    assert end_state == ConversationHandler.END
    assert len(trim_calls) == 1
    assert trim_calls[0]["start"] == 0
    assert trim_calls[0]["end"] == 55
    context.bot.send_video_note.assert_called_once()
    assert context.user_data == {}


@pytest.mark.asyncio
async def test_e2e_scenario_02_custom_timecode(
    context_factory,
    message_update_factory,
    callback_update_factory,
):
    context = context_factory()

    await _search_and_select(
        query=REAL_TRACK_QUERY,
        context=context,
        message_update_factory=message_update_factory,
        callback_update_factory=callback_update_factory,
    )

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

    custom_state = await handlers.set_custom_time(
        message_update_factory(text="00:30 01:10"),
        context,
    )
    assert custom_state == ConversationHandler.END
    assert context.user_data[st.DURATION_LEFT_BORDER] == "30"
    assert context.user_data[st.DURATION_RIGHT_BORDER] == "70"

    trim_calls: list[dict[str, Any]] = []
    real_trim_audio = handlers.api_utils.trim_audio

    async def trim_spy(*args, **kwargs):
        trim_calls.append(kwargs.copy())
        return await real_trim_audio(*args, **kwargs)

    with patch("src.handlers.api_utils.trim_audio", side_effect=trim_spy):
        end_state = await handlers.create_video_message(
            callback_update_factory(data=st.CREATE_VIDEO_MESSAGE),
            context,
        )

    assert end_state == ConversationHandler.END
    assert len(trim_calls) == 1
    assert trim_calls[0]["start"] == 30
    assert trim_calls[0]["end"] == 70
    context.bot.send_video_note.assert_called_once()


@pytest.mark.asyncio
async def test_e2e_scenario_03_empty_search_then_retry(
    context_factory,
    message_update_factory,
):
    context = context_factory()

    real_search = handlers.api_utils.search_for_tracks
    attempts = {"count": 0}

    async def search_with_one_empty_then_real(track_name: str):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return []
        return await real_search(track_name)

    empty_update = message_update_factory(
        text=f"nonexistent_{uuid.uuid4().hex}",
    )
    retry_update = message_update_factory(text=REAL_TRACK_QUERY)

    with patch(
        "src.handlers.api_utils.search_for_tracks",
        side_effect=search_with_one_empty_then_real,
    ):
        first_state = await handlers.search_audio_by_name(
            empty_update,
            context,
        )
        second_state = await handlers.search_audio_by_name(
            retry_update,
            context,
        )

    assert first_state is None
    empty_update.message.reply_text.assert_called_once_with(
        "Ничего не получилось найти. Попробуйте написать еще раз."
    )

    assert second_state == st.SELECTING_SONG
    retry_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_e2e_scenario_04_search_unavailable_then_recovered(
    context_factory,
    message_update_factory,
):
    context = context_factory()
    real_search = handlers.api_utils.search_for_tracks
    attempts = {"count": 0}

    async def search_with_one_failure_then_real(track_name: str):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return None
        return await real_search(track_name)

    failed_update = message_update_factory(text="nonexistent_track_12345")
    recovered_update = message_update_factory(text=REAL_TRACK_QUERY)

    with patch(
        "src.handlers.api_utils.search_for_tracks",
        side_effect=search_with_one_failure_then_real,
    ):
        first_state = await handlers.search_audio_by_name(
            failed_update,
            context,
        )
        second_state = await handlers.search_audio_by_name(
            recovered_update,
            context,
        )

    assert first_state is None
    failed_update.message.reply_text.assert_called_once_with(
        "Произошла ошибка. Попробуйте еще раз позже."
    )

    assert second_state == st.SELECTING_SONG
    recovered_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_e2e_scenario_05_invalid_time_interval_then_success(
    context_factory,
    message_update_factory,
    callback_update_factory,
):
    context = context_factory()

    await _search_and_select(
        query=REAL_TRACK_QUERY,
        context=context,
        message_update_factory=message_update_factory,
        callback_update_factory=callback_update_factory,
    )

    await handlers.print_time_codes(
        callback_update_factory(data=st.SET_TIME_CODE),
        context,
    )
    await handlers.print_custom_time_text(
        callback_update_factory(data=st.DURATION_CUSTOM),
        context,
    )

    invalid_order_input = message_update_factory(text="01:00 00:30")
    invalid_order_state = await handlers.set_custom_time(
        invalid_order_input,
        context,
    )

    assert invalid_order_state == st.INPUT_TIME_CODE
    invalid_order_input.message.reply_text.assert_called_once()
    invalid_reply = invalid_order_input.message.reply_text.call_args.args[0]
    assert "ошиб" in invalid_reply.lower()

    too_long_input = message_update_factory(text="00:00 01:00")
    too_long_state = await handlers.set_custom_time(too_long_input, context)

    assert too_long_state == st.INPUT_TIME_CODE
    too_long_input.message.reply_text.assert_called_once()
    too_long_reply = too_long_input.message.reply_text.call_args.args[0]
    assert "55" in too_long_reply

    valid_input = message_update_factory(text="00:10 00:50")
    valid_state = await handlers.set_custom_time(valid_input, context)

    assert valid_state == ConversationHandler.END
    assert context.user_data[st.DURATION_LEFT_BORDER] == "10"
    assert context.user_data[st.DURATION_RIGHT_BORDER] == "50"


@pytest.mark.asyncio
async def test_e2e_scenario_06_cover_unavailable(
    context_factory,
    message_update_factory,
    callback_update_factory,
):
    context = context_factory()

    await _search_and_select(
        query=REAL_TRACK_QUERY,
        context=context,
        message_update_factory=message_update_factory,
        callback_update_factory=callback_update_factory,
    )

    real_create_video = handlers.api_utils.create_video
    captured_image_paths: list[str] = []

    async def create_video_spy(*args, **kwargs):
        captured_image_paths.append(kwargs["image_path"])
        return await real_create_video(*args, **kwargs)

    with (
        patch(
            "src.handlers.api_utils.download_cover",
            AsyncMock(return_value=""),
        ),
        patch(
            "src.handlers.api_utils.create_video",
            side_effect=create_video_spy,
        ),
    ):
        end_state = await handlers.create_video_message(
            callback_update_factory(data=st.CREATE_VIDEO_MESSAGE),
            context,
        )

    assert end_state == ConversationHandler.END
    assert captured_image_paths[-1] == "video_note_images/vinyl_default.jpg"
    context.bot.send_video_note.assert_called_once()


@pytest.mark.asyncio
async def test_e2e_scenario_07_media_processing_error(
    context_factory,
    message_update_factory,
    callback_update_factory,
):
    context = context_factory()

    await _search_and_select(
        query=REAL_TRACK_QUERY,
        context=context,
        message_update_factory=message_update_factory,
        callback_update_factory=callback_update_factory,
    )

    update = callback_update_factory(data=st.CREATE_VIDEO_MESSAGE)
    with patch(
        "src.handlers.api_utils.trim_audio",
        AsyncMock(return_value=False),
    ):
        end_state = await handlers.create_video_message(update, context)

    assert end_state == ConversationHandler.END
    assert update.callback_query.edit_message_text.call_count == 3
    assert "Ошибка, при создании кружка" in _extract_edited_text(
        update.callback_query.edit_message_text
    )
    context.bot.send_video_note.assert_not_called()


@pytest.mark.asyncio
async def test_e2e_scenario_08_database_down(
    context_factory,
    message_update_factory,
    callback_update_factory,
):
    context = context_factory()

    mock_log = AsyncMock(return_value=False)
    with patch("src.handlers.db_utils.log_interaction", mock_log):
        await _search_and_select(
            query=REAL_TRACK_QUERY,
            context=context,
            message_update_factory=message_update_factory,
            callback_update_factory=callback_update_factory,
        )

        end_state = await handlers.create_video_message(
            callback_update_factory(data=st.CREATE_VIDEO_MESSAGE),
            context,
        )

    assert end_state == ConversationHandler.END
    assert mock_log.await_count == 2
    context.bot.send_video_note.assert_called_once()


@pytest.mark.asyncio
async def test_e2e_scenario_09_parallel_users_sessions(
    context_factory,
    message_update_factory,
    callback_update_factory,
):
    users = [
        {
            "query_candidates": [REAL_TRACK_QUERY, *ALT_TRACK_QUERIES],
            "user_id": 1001,
            "chat_id": 9001,
            "start": 5,
            "end": 25,
        },
        {
            "query_candidates": [*ALT_TRACK_QUERIES, REAL_TRACK_QUERY],
            "user_id": 1002,
            "chat_id": 9002,
            "start": 10,
            "end": 30,
        },
    ]

    trim_calls: list[dict[str, Any]] = []
    real_trim_audio = handlers.api_utils.trim_audio

    async def trim_spy(*args, **kwargs):
        trim_calls.append(kwargs.copy())
        return await real_trim_audio(*args, **kwargs)

    async def run_flow(user_case: dict[str, Any]):
        user_id = user_case["user_id"]
        chat_id = user_case["chat_id"]
        start_value = user_case["start"]
        end_value = user_case["end"]

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

        await _search_and_select_with_fallback(
            queries=user_case["query_candidates"],
            context=context,
            message_update_factory=message_update_factory,
            callback_update_factory=callback_update_factory,
            user_id=user_id,
            username=f"u{user_id}",
            chat_id=chat_id,
        )

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
        return context, user_case

    with patch("src.handlers.api_utils.trim_audio", side_effect=trim_spy):
        results = await asyncio.gather(
            *[run_flow(user_case) for user_case in users]
        )

    assert len(results) == 2

    for context, user_case in results:
        context.bot.send_video_note.assert_called_once()
        send_kwargs = context.bot.send_video_note.call_args.kwargs
        assert send_kwargs["chat_id"] == user_case["chat_id"]
        assert context.user_data == {}

    actual_calls = {(call["start"], call["end"]) for call in trim_calls}
    expected_calls = {
        (user_case["start"], user_case["end"])
        for user_case in users
    }
    assert expected_calls.issubset(actual_calls)


@pytest.mark.asyncio
async def test_e2e_scenario_10_second_full_cycle_without_restart(
    context_factory,
    message_update_factory,
    callback_update_factory,
):
    context = context_factory()
    trim_calls: list[dict[str, Any]] = []
    real_trim_audio = handlers.api_utils.trim_audio

    async def trim_spy(*args, **kwargs):
        trim_calls.append(kwargs.copy())
        return await real_trim_audio(*args, **kwargs)

    async def run_cycle(queries: Sequence[str], time_code: str):
        await _search_and_select_with_fallback(
            queries=queries,
            context=context,
            message_update_factory=message_update_factory,
            callback_update_factory=callback_update_factory,
        )

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

    with patch("src.handlers.api_utils.trim_audio", side_effect=trim_spy):
        await run_cycle([REAL_TRACK_QUERY, *ALT_TRACK_QUERIES], "00:05 00:35")

        restart_state = await handlers.restart_conversation(
            callback_update_factory(data=st.RESTART_SEARCH),
            context,
        )
        assert restart_state == st.TYPING_SONG_NAME

        await run_cycle([*ALT_TRACK_QUERIES, REAL_TRACK_QUERY], "00:40 01:10")

    assert context.bot.send_video_note.call_count == 2
    assert len(trim_calls) >= 2
    assert (trim_calls[0]["start"], trim_calls[0]["end"]) == (5, 35)
    assert (trim_calls[1]["start"], trim_calls[1]["end"]) == (40, 70)
