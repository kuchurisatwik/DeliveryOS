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
    OPENROUTER_API_KEY: Optional[str] = Field(None, description="OpenRouter API Key")

    # SonarQube settings (Layer 4 Quality Gate)
    SONARQUBE_URL: str = Field(
        default="https://sonarcloud.io",
        description="Base URL of the SonarQube / SonarCloud instance",
    )
    SONARQUBE_TOKEN: Optional[str] = Field(
        None, description="SonarQube project analysis token (used as HTTP Basic auth user)"
    )
    SONARQUBE_PROJECT_KEY: Optional[str] = Field(
        None, description="SonarQube project key whose metrics back the Quality Gate"
    )
    
    # Pipeline selection
    PIPELINE_MODE: str = Field(
        default="both",
        description=(
            "Which pipeline(s) to run on a push: 'security' (security pipeline "
            "only), 'testing' (test-generation/validation pipeline only), or "
            "'both' (default)."
        ),
    )

    # Workspace settings
    WORKSPACE_DIR: str = Field(
        default=os.path.join(os.getcwd(), "workspace"), 
        description="Local directory for cloning repositories"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
