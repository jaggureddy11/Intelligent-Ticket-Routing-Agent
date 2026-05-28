import os
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure local .env file gets loaded into environment variables
load_dotenv()

class Settings(BaseSettings):
    # App Settings
    ENV: str = "development"
    PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./ticket_routing.db"
    ALLOWED_ORIGINS: list[str] = ["*"]
    LOG_LEVEL: str = "INFO"
    
    # Hugging Face Settings
    # Generate one at: https://huggingface.co/settings/tokens
    HF_TOKEN: Optional[str] = None
    HF_MODEL: str = "meta-llama/Llama-3.2-3B-Instruct"

    # Settings configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
