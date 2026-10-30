from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Task API"

    postgres_user: str = "postgres"
    postgres_password: str
    postgres_host: str = "localhost"
    postgres_port: int = 8081
    postgres_db: str = "postgres"

    access_token_expire_minutes: int = 30
    secret: str

    model_config = SettingsConfigDict(env_file=".env")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
