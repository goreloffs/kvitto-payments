from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # По умолчанию — SQLite-файл в корне проекта.
    # В тестах переопределим через переменную окружения DATABASE_URL.
    database_url: str = "sqlite:///./kvitto.db"

    # Секрет для проверки подписи вебхука (бонусная часть).
    # В репо его нет, читаем из .env. Если не задан — проверка отключена.
    webhook_secret: str | None = None


settings = Settings()
