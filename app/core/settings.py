from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DATABASE_URL: str
    HMAC_SECRET: str
    IDMP_TTL_SECONDS: int = 86400

settings = Settings()
