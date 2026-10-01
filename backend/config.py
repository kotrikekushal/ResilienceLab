from pydantic_settings import BaseSettings, SettingsConfigDict
import os


APP_ENV = os.getenv("APP_ENV", "local")

ENV_FILES = {
    "local": ".env",
    "docker": ".env.docker",
}


class Settings(BaseSettings):
    DATABASE_URL: str
    TEST_DATABASE_URL: str
    REDIS_BROKER_URL: str
    REDIS_RESULT_BACKEND: str

    model_config = SettingsConfigDict(
        env_file=ENV_FILES.get(APP_ENV, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()