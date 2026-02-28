import pytest
from datetime import datetime
from pydantic import ValidationError

from database.models import (
    InteractionTypeEnum,
    UserCreate,
    User,
    InteractionCreate,
    InteractionResponse,
    InteractionType,
)


class TestInteractionTypeEnum:

    def test_enum_values(self):
        assert InteractionTypeEnum.SEARCH_SONG == "Поиск песни"
        assert InteractionTypeEnum.CREATE_VIDEO == "Создание видео"

    def test_enum_has_exactly_two_members(self):
        assert len(InteractionTypeEnum) == 2


class TestUserCreate:

    def test_valid_user_create(self):
        user = UserCreate(user_id=12345, username="testuser")
        assert user.user_id == 12345
        assert user.username == "testuser"

    def test_user_create_without_username(self):
        user = UserCreate(user_id=12345)
        assert user.user_id == 12345
        assert user.username is None

    def test_user_create_invalid_missing_user_id(self):
        with pytest.raises(ValidationError):
            UserCreate(username="test")


class TestUser:

    def test_valid_user(self):
        user = User(user_id=99, username="alice")
        assert user.user_id == 99
        assert user.username == "alice"

    def test_user_without_username(self):
        user = User(user_id=99)
        assert user.username is None


class TestInteractionCreate:

    def test_valid_interaction_create_search(self):
        ic = InteractionCreate(
            user_id=1,
            username="bob",
            interaction_type=InteractionTypeEnum.SEARCH_SONG,
        )
        assert ic.interaction_type == InteractionTypeEnum.SEARCH_SONG

    def test_valid_interaction_create_video(self):
        ic = InteractionCreate(
            user_id=1,
            interaction_type=InteractionTypeEnum.CREATE_VIDEO,
        )
        assert ic.interaction_type == InteractionTypeEnum.CREATE_VIDEO

    def test_interaction_create_invalid_type(self):
        with pytest.raises(ValidationError):
            InteractionCreate(
                user_id=1,
                interaction_type="INVALID_TYPE",
            )


class TestInteractionResponse:

    def test_valid_interaction_response(self):
        now = datetime.now()
        resp = InteractionResponse(
            interaction_id=1,
            user_id=100,
            username="charlie",
            interaction_type="Поиск песни",
            interaction_date=now,
        )
        assert resp.interaction_id == 1
        assert resp.user_id == 100
        assert resp.interaction_date == now

    def test_interaction_response_none_username(self):
        resp = InteractionResponse(
            interaction_id=2,
            user_id=200,
            username=None,
            interaction_type="Создание видео",
            interaction_date=datetime.now(),
        )
        assert resp.username is None


class TestInteractionType:

    def test_valid_interaction_type(self):
        it = InteractionType(type_id=1, interaction_type="Поиск песни")
        assert it.type_id == 1
        assert it.interaction_type == "Поиск песни"
