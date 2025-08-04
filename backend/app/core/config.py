from pydantic_settings import BaseSettings
from typing import Optional, List
from enum import Enum


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    # Environment
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    
    # Database
    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout: int = 30
    
    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    password_min_length: int = 6
    
    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4.1"
    openai_temperature: float = 0.7
    openai_max_tokens: Optional[int] = None
    openai_timeout: int = 60
    
    # LLM API Keys for LangGraph
    anthropic_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    
    # LangSmith tracing configuration
    langsmith_tracing: Optional[str] = None
    langsmith_endpoint: Optional[str] = None
    langsmith_api_key: Optional[str] = None
    langsmith_project: Optional[str] = None
    
    # Rate Limiting
    rate_limit_enabled: bool = True
    redis_url: Optional[str] = "redis://localhost:6379"
    
    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json or console
    
    # Monitoring
    metrics_enabled: bool = True
    health_check_interval: int = 30
    
    # Application
    app_name: str = "Chat App API"
    app_version: str = "1.2.0"
    app_description: str = "Enhanced chat application with LangGraph and GPT-4.1"
    
    # File upload (for future features)
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: List[str] = [".txt", ".pdf", ".doc", ".docx"]
    
    # Chat settings
    max_chat_history: int = 100
    max_message_length: int = 4000
    chat_title_max_length: int = 100
    
    # Session management
    session_timeout_minutes: int = 1440  # 24 hours
    max_concurrent_sessions: int = 5
    
    # Production settings
    workers: int = 4
    host: str = "0.0.0.0"
    port: int = 8000
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_testing(self) -> bool:
        return self.environment == Environment.TESTING
    
    def get_cors_config(self) -> dict:
        """Get CORS configuration"""
        return {
            "allow_origins": self.cors_origins,
            "allow_credentials": self.cors_allow_credentials,
            "allow_methods": self.cors_allow_methods,
            "allow_headers": self.cors_allow_headers,
        }
    
    def get_database_config(self) -> dict:
        """Get database configuration"""
        return {
            "url": self.database_url,
            "pool_size": self.database_pool_size,
            "max_overflow": self.database_max_overflow,
            "pool_timeout": self.database_pool_timeout,
        }
    
    def get_openai_config(self) -> dict:
        """Get OpenAI configuration"""
        return {
            "api_key": self.openai_api_key,
            "model": self.openai_model,
            "temperature": self.openai_temperature,
            "max_tokens": self.openai_max_tokens,
            "timeout": self.openai_timeout,
        }
    
    def get_langgraph_config(self) -> dict:
        """Get LangGraph configuration"""
        return {
            "anthropic_api_key": self.anthropic_api_key,
            "tavily_api_key": self.tavily_api_key,
            "openai_api_key": self.openai_api_key,
        }


# Global settings instance
settings = Settings()


# Environment-specific configurations
def get_environment_config():
    """Get environment-specific configuration overrides"""
    if settings.is_production:
        return {
            "debug": False,
            "log_level": "WARNING",
            "rate_limit_enabled": True,
            "metrics_enabled": True,
        }
    elif settings.is_testing:
        return {
            "debug": False,
            "log_level": "DEBUG",
            "database_url": settings.database_url.replace("chatdb", "chatdb_test"),
            "rate_limit_enabled": False,
        }
    else:  # development
        return {
            "debug": True,
            "log_level": "DEBUG",
            "rate_limit_enabled": False,
        }


# Apply environment-specific settings
env_config = get_environment_config()
for key, value in env_config.items():
    if hasattr(settings, key):
        setattr(settings, key, value) 