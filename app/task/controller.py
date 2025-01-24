from fastapi import APIRouter, Body, Depends, Query, Path
from typing import Annotated
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from app.user.controller import check_jwt
from app.task.model import Task
from app.db import get_session

router = APIRouter()
UserDep = Annotated[dict, Depends(check_jwt)]
SessionDep = Annotated[Session, Depends(get_session)]

class TaskModel(BaseModel):
    name: str = Field(min_length=2)
    duration: int
    user_id: int

@router.post("/task", tags=["task"])
async def create_task(task: Annotated[TaskModel, Body()], user: UserDep, session: SessionDep):
    _task = Task(
        name=task.name,
        duration=task.duration,
        user_id=user.get("id", None)
    )
    session.add(_task)
    session.commit()
    session.refresh(_task)
    return {"omg": 1, "task": task, "user": user}

@router.get("/task", tags=["task"])
async def get_tasks_by_user(user: UserDep, session: SessionDep):
    statement = select(Task).where(Task.user_id == user.get("id", None))
    tasks = session.exec(statement).fetchall()
    return {"tasks": tasks, "user_id": user.get("id", None)}

@router.put("/task", tags=["task"])
async def put_task_by_id(task: Annotated[Task, Body()], __: UserDep, session: SessionDep):
    statement = select(Task).where(Task.id == task.id)
    _task = session.exec(statement).first()
    task_dict = task.model_dump()
    attributes_list = [a for a in task_dict.keys()]

    for attribute in attributes_list:
        setattr(_task, attribute, getattr(task, attribute))
    session.add(_task)
    session.commit()
    session.refresh(_task)
    return {"update": 1, "task": _task}

@router.delete("/task/{task_id}", tags=["task"])
async def delete_task_by_id(task_id: Annotated[int, Path()], __: UserDep, session: SessionDep):
    statement = select(Task).where(Task.id == task_id)
    _task = session.exec(statement).one()
    session.delete(_task)
    session.commit()
    return {"deleted":1, "deleted task": _task}
