from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    KRAKEN_API_KEY: str
    KRAKEN_API_SECRET: str
    SQLALCHEMY_DATABASE_URI: str
    SECRET_KEY: str
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_BOT_USERNAME: str


settings = Settings()
