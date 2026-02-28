import pytest
from database.models import UserCreate, InteractionCreate, InteractionTypeEnum
from database.services import UserService, InteractionService


class TestUserService:

    def test_create_user(self, patched_db):
        user_data = UserCreate(user_id=100, username="alice")
        user = UserService.create_or_update_user(user_data)
        assert user.user_id == 100
        assert user.username == "alice"

    def test_create_user_without_username(self, patched_db):
        user_data = UserCreate(user_id=101)
        user = UserService.create_or_update_user(user_data)
        assert user.user_id == 101
        assert user.username is None

    def test_update_existing_user(self, patched_db):
        user_data_v1 = UserCreate(user_id=100, username="alice")
        UserService.create_or_update_user(user_data_v1)

        user_data_v2 = UserCreate(user_id=100, username="alice_updated")
        user = UserService.create_or_update_user(user_data_v2)
        assert user.username == "alice_updated"

        fetched = UserService.get_user(100)
        assert fetched is not None
        assert fetched.username == "alice_updated"

    def test_get_user_found(self, patched_db):
        UserService.create_or_update_user(UserCreate(user_id=200, username="bob"))
        user = UserService.get_user(200)
        assert user is not None
        assert user.user_id == 200
        assert user.username == "bob"

    def test_get_user_not_found(self, patched_db):
        user = UserService.get_user(999999)
        assert user is None


class TestInteractionService:

    def test_log_interaction_search(self, patched_db):
        interaction_data = InteractionCreate(
            user_id=300,
            username="charlie",
            interaction_type=InteractionTypeEnum.SEARCH_SONG,
        )
        resp = InteractionService.log_interaction(interaction_data)
        assert resp.interaction_id is not None
        assert resp.user_id == 300
        assert resp.username == "charlie"
        assert resp.interaction_type == "Поиск песни"

    def test_log_interaction_create_video(self, patched_db):
        interaction_data = InteractionCreate(
            user_id=301,
            username="dave",
            interaction_type=InteractionTypeEnum.CREATE_VIDEO,
        )
        resp = InteractionService.log_interaction(interaction_data)
        assert resp.interaction_type == "Создание видео"

    def test_log_interaction_creates_user_automatically(self, patched_db):
        interaction_data = InteractionCreate(
            user_id=400,
            username="eve",
            interaction_type=InteractionTypeEnum.SEARCH_SONG,
        )
        InteractionService.log_interaction(interaction_data)

        user = UserService.get_user(400)
        assert user is not None
        assert user.username == "eve"

    def test_get_user_interactions_with_data(self, patched_db):
        ic = InteractionCreate(
            user_id=500,
            username="frank",
            interaction_type=InteractionTypeEnum.SEARCH_SONG,
        )
        InteractionService.log_interaction(ic)
        InteractionService.log_interaction(
            InteractionCreate(
                user_id=500,
                username="frank",
                interaction_type=InteractionTypeEnum.CREATE_VIDEO,
            )
        )

        interactions = InteractionService.get_user_interactions(500)
        assert len(interactions) == 2
        types = {i.interaction_type for i in interactions}
        assert "Поиск песни" in types
        assert "Создание видео" in types

    def test_get_user_interactions_empty(self, patched_db):
        interactions = InteractionService.get_user_interactions(999998)
        assert interactions == []

    def test_get_all_interactions(self, patched_db):
        InteractionService.log_interaction(
            InteractionCreate(
                user_id=600,
                username="grace",
                interaction_type=InteractionTypeEnum.SEARCH_SONG,
            )
        )
        InteractionService.log_interaction(
            InteractionCreate(
                user_id=601,
                username="heidi",
                interaction_type=InteractionTypeEnum.CREATE_VIDEO,
            )
        )

        all_interactions = InteractionService.get_all_interactions()
        assert len(all_interactions) >= 2

    def test_get_all_interactions_empty(self, patched_db):
        patched_db.execute("DELETE FROM interactions")
        patched_db.commit()

        all_interactions = InteractionService.get_all_interactions()
        assert all_interactions == []
