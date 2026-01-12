"""
Configuration management.
Simple .env based config for VPS deployment.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    
    # Security
    session_secret: str = "change-me-in-production-use-random-string"
    admin_password_hash: str = ""  # bcrypt hash
    
    # Database
    database_path: str = "./data/app.db"
    
    # Logging
    log_level: str = "INFO"


# Global settings instance
settings = Settings()
