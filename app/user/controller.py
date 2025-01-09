from typing import Annotated
from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

class User(BaseModel):
    password: str = Field(min_length=8)
    name: str = Field(min_length=4, max_length=20)

router = APIRouter()

@router.get("/singin", tags=["users"])
async def register(user: Annotated[User, Body()]):
    return {
        "password": user.password,
        "name": user.name
    }
