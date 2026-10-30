from contextlib import asynccontextmanager

# import uvicorn
from fastapi import FastAPI

from app.db import create_db_and_tables
from app.task import controller as task_controller
from app.user import controller as user_controller


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("it begins")
    create_db_and_tables()
    yield
    print("byee!")


app = FastAPI(lifespan=lifespan)

app.include_router(user_controller.router)
app.include_router(task_controller.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "version": "0.2"}


@app.get("/")
async def hello():
    return {"omg": 1}
