import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Task API"
    POSTGRES_PASSWORD: str

    model_config = SettingsConfigDict(env_file=".env")

def define_env_variables():
    settings = Settings()
    os.environ["POSTGRES_PASSWORD"] = settings.POSTGRES_PASSWORD
    print("omg env variables are configured")

define_env_variables()

