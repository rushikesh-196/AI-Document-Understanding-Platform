"""
Application Configuration
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl


class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database Configuration
    DATABASE_URL: str = "sqlite:///./document_ai.db"
    
    # CORS Configuration
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # File Upload Configuration
    MAX_UPLOAD_SIZE: int = 16777216  # 16MB
    UPLOAD_DIR: str = "./uploads"
    EXPORT_DIR: str = "./exports"
    
    # AI Model Configuration
    DEVICE: str = "cpu"
    CACHE_DIR: str = "./models_cache"
    CLASSIFICATION_MODEL: str = "microsoft/layoutlmv3-base"
    OCR_ENGINE: str = "paddle"
    NER_MODEL: str = "en_core_web_sm"
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
