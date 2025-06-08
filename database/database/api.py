from fastapi import APIRouter, HTTPException
from typing import List
from database.models import (
    User, InteractionCreate, InteractionResponse
)
from database.services import UserService, InteractionService

router = APIRouter()

@router.post("/log-interaction/", response_model=InteractionResponse)
async def log_user_interaction(interaction: InteractionCreate):
    """
    Логирование взаимодействия пользователя.
    
    Создает пользователя (если не существует) и записывает взаимодействие.
    """
    try:
        return InteractionService.log_interaction(interaction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int):
    """Получение пользователя по ID."""
    user = UserService.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/interactions/user/{user_id}", response_model=List[InteractionResponse])
async def get_user_interactions(user_id: int):
    """Получение всех взаимодействий пользователя."""
    return InteractionService.get_user_interactions(user_id)

@router.get("/interactions/", response_model=List[InteractionResponse])
async def get_all_interactions():
    """Получение всех взаимодействий."""
    return InteractionService.get_all_interactions()

# Health check endpoint
@router.get("/health")
async def health_check():
    """Проверка состояния сервиса."""
    return {"status": "healthy"}