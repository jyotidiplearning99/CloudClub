"""
Application configuration with ALL required fields.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""
    
    # OpenAI
    openai_api_key: str
    llm_model: str = "gpt-4o"
    llm_max_tokens: int = 16000  # FIXED: Was 25000, now 16000 (safe for gpt-4o)
    llm_temperature: float = 0.0  # Temperature for LLM
    
    # Resume parsing
    max_resume_length: int = 30000  # characters
    
    # API
    api_title: str = "Cloud Club Resume Parser"
    api_version: str = "1.0.0"
    debug: bool = False  # ADD THIS LINE - fixes the AttributeError
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
