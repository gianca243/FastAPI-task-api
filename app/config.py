import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Task API"
    POSTGRES_PASSWORD: str
    ACCESS_TOKEN_EXPIRE_MINUTES: str
    SECRET: str

    model_config = SettingsConfigDict(env_file=".env")

def define_env_variables():
    settings = Settings()
    os.environ["POSTGRES_PASSWORD"] = settings.POSTGRES_PASSWORD
    os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    os.environ["SECRET"] = settings.SECRET
    print("omg env variables are configured")

define_env_variables()
