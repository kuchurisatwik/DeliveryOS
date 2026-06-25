from pydantic_settings import BaseSettings
from pydantic import Field
import os
from typing import Optional

class Settings(BaseSettings):
    """Application configuration settings."""
    # Webhook settings
    WEBHOOK_SECRET: Optional[str] = Field(None, description="GitHub webhook secret for validation")
    
    # GitHub settings
    GITHUB_TOKEN: Optional[str] = Field(None, description="GitHub Personal Access Token")
    
    # AI settings
    GEMINI_API_KEY: Optional[str] = Field(None, description="Google Gemini API Key")
    
    # Workspace settings
    WORKSPACE_DIR: str = Field(
        default=os.path.join(os.getcwd(), "workspace"), 
        description="Local directory for cloning repositories"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
