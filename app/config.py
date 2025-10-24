"""
Application configuration.
Loads settings from environment variables.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""
    
    # App Settings (ADD THIS SECTION)
    debug: bool = False  # <-- THIS IS THE LINE YOU NEED TO ADD
    
    # OpenAI Configuration
    openai_api_key: str
    llm_model: str = "gpt-4o-2024-08-06"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4000
    
    # Parsing Configuration
    max_resume_length: int = 8000
    
    # Optional: Database
    database_url: str = "postgresql://app:app@localhost:5432/cloudclub"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
