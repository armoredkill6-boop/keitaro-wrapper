from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    keitaro_base_url: str = "https://tlgk.host"
    keitaro_api_key: str = ""
    database_url: str = "postgresql+psycopg://keitaro:keitaro@localhost:5432/keitaro_wrapper"
    campaign_name_prefix: str = "test_krylov_"
    google_redirect_url: str = "https://www.google.com/"


settings = Settings()