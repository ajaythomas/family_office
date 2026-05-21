from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    database_url_test: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    jwt_secret: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]
    app_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"


settings = Settings()
