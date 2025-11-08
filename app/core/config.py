from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str
    
    # Firebase
    firebase_project_id: str
    firebase_credentials_path: str
    
    # API
    api_v1_str: str = "/api/v1"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Environment
    environment: str = "development"
    debug: bool = True
    
    # Encryption
    encryption_key: str
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

