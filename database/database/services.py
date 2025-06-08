import sqlite3
from typing import List, Optional
from datetime import datetime
from database.db import get_db_connection
from database.models import (
    User, UserCreate, 
    InteractionCreate, InteractionResponse,
    InteractionTypeEnum
)

class UserService:
    @staticmethod
    def create_or_update_user(user_data: UserCreate) -> User:
        """Создание или обновление пользователя."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO users (user_id, username) 
                VALUES (?, ?)
            """, (user_data.user_id, user_data.username))
            conn.commit()
            return User(**user_data.dict())
    
    @staticmethod
    def get_user(user_id: int) -> Optional[User]:
        """Получение пользователя по ID."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return User(user_id=row["user_id"], username=row["username"])
            return None

class InteractionService:
    @staticmethod
    def log_interaction(interaction_data: InteractionCreate) -> InteractionResponse:
        """Логирование взаимодействия пользователя."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Создаем или обновляем пользователя
            cursor.execute("""
                INSERT OR REPLACE INTO users (user_id, username) 
                VALUES (?, ?)
            """, (interaction_data.user_id, interaction_data.username))
            
            # Получаем ID типа взаимодействия
            cursor.execute("""
                SELECT type_id FROM interaction_types WHERE interaction_type = ?
            """, (interaction_data.interaction_type.value,))
            type_row = cursor.fetchone()
            
            if not type_row:
                raise ValueError(f"Interaction type '{interaction_data.interaction_type.value}' not found")
            
            interaction_type_id = type_row["type_id"]
            
            # Создаем запись о взаимодействии
            cursor.execute("""
                INSERT INTO interactions (user_id, interaction_type_id) 
                VALUES (?, ?)
            """, (interaction_data.user_id, interaction_type_id))
            
            interaction_id = cursor.lastrowid
            conn.commit()
            
            return InteractionResponse(
                interaction_id=interaction_id,
                user_id=interaction_data.user_id,
                username=interaction_data.username,
                interaction_type=interaction_data.interaction_type.value,
                interaction_date=datetime.now()
            )
    
    @staticmethod
    def get_user_interactions(user_id: int) -> List[InteractionResponse]:
        """Получение всех взаимодействий пользователя."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    i.interaction_id,
                    i.user_id,
                    u.username,
                    it.interaction_type,
                    i.interaction_date
                FROM interactions i
                JOIN users u ON i.user_id = u.user_id
                JOIN interaction_types it ON i.interaction_type_id = it.type_id
                WHERE i.user_id = ?
                ORDER BY i.interaction_date DESC
            """, (user_id,))
            
            rows = cursor.fetchall()
            return [
                InteractionResponse(
                    interaction_id=row["interaction_id"],
                    user_id=row["user_id"],
                    username=row["username"],
                    interaction_type=row["interaction_type"],
                    interaction_date=datetime.fromisoformat(row["interaction_date"])
                ) for row in rows
            ]
    
    @staticmethod
    def get_all_interactions() -> List[InteractionResponse]:
        """Получение всех взаимодействий."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    i.interaction_id,
                    i.user_id,
                    u.username,
                    it.interaction_type,
                    i.interaction_date
                FROM interactions i
                JOIN users u ON i.user_id = u.user_id
                JOIN interaction_types it ON i.interaction_type_id = it.type_id
                ORDER BY i.interaction_date DESC
            """)
            
            rows = cursor.fetchall()
            return [
                InteractionResponse(
                    interaction_id=row["interaction_id"],
                    user_id=row["user_id"],
                    username=row["username"],
                    interaction_type=row["interaction_type"],
                    interaction_date=datetime.fromisoformat(row["interaction_date"])
                ) for row in rows
            ]