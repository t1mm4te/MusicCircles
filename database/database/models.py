from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum

class InteractionTypeEnum(str, Enum):
    SEARCH_SONG = "Поиск песни"
    CREATE_VIDEO = "Создание видео"

class UserCreate(BaseModel):
    user_id: int
    username: Optional[str] = None

class User(BaseModel):
    user_id: int
    username: Optional[str] = None

class InteractionCreate(BaseModel):
    user_id: int
    username: Optional[str] = None
    interaction_type: InteractionTypeEnum

class InteractionResponse(BaseModel):
    interaction_id: int
    user_id: int
    username: Optional[str]
    interaction_type: str
    interaction_date: datetime

class InteractionType(BaseModel):
    type_id: int
    interaction_type: str