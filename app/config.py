from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    database_url_test: str = ""
    google_client_id: str = ""
    jwt_secret: str = ""


settings = Settings()
