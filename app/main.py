from contextlib import asynccontextmanager

import app.config
# import uvicorn
from fastapi import FastAPI
from app.user import controller as user_controller
from app.task import controller as task_controller
from app.db import create_db_and_tables



@asynccontextmanager
async def lifespan(app: FastAPI):
    print("it begins")
    create_db_and_tables()
    yield
    print("byee!")

app = FastAPI(lifespan=lifespan)

app.include_router(user_controller.router)
app.include_router(task_controller.router)

@app.get("/")
async def hello():
    return {"omg":1}

# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)
