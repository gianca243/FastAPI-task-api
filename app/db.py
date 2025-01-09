import os

from sqlmodel import create_engine, SQLModel, Session

PASSWORD = os.environ["POSTGRES_PASSWORD"]
postgesql_url = f"postgresql://postgres:{PASSWORD}@localhost:8081/postgres"

connect_args = {"check_same_thread": False}
engine = create_engine(postgesql_url, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
