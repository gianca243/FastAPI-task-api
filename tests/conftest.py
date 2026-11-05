import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Settings exige estas variables. En tu máquina vienen del .env, pero en el CI no
# hay .env. setdefault solo las pone si no existen.
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("SECRET", "test-secret")


@pytest.fixture
def fastapi_app():
    # Import "tardío": así las variables de arriba ya existen cuando se lee Settings.
    # Importar main también registra los modelos (User, Task) en SQLModel.metadata.
    from app.main import app

    return app


@pytest.fixture
def session(fastapi_app):
    # "sqlite://" sin archivo = BD en memoria. StaticPool hace que todas las
    # conexiones compartan esa misma BD (si no, cada conexión vería una vacía).
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session  # el test corre aquí; al terminar, la BD desaparece


@pytest.fixture
def client(fastapi_app, session):
    from app.db import get_session

    fastapi_app.dependency_overrides[get_session] = lambda: session
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()
