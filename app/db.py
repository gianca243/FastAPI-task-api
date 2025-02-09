import os

from sqlmodel import create_engine, SQLModel, Session

PASSWORD = os.environ["POSTGRES_PASSWORD"]
postgesql_url = f"postgresql://postgres:{PASSWORD}@localhost:8081/postgres"


engine = create_engine(postgesql_url)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
