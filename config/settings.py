import os
from typing import Optional

class Settings:
    """Application settings and configurations"""
    
    # Database settings
    MONGO_URL: str = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    DB_NAME: str = os.getenv("DB_NAME", "telegram_bot_db")
    
    # OpenAI settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL_DEFAULT: str = "gpt-4o"
    OPENAI_MODEL_FALLBACK: str = "gpt-4o-mini"
    
    # Telegram settings
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_WEBHOOK_URL: str = os.getenv("TELEGRAM_WEBHOOK_URL", "")
    
    # Feature flags
    ENABLE_FOOD_ANALYSIS: bool = True
    ENABLE_MOVIE_EXPERT: bool = True
    ENABLE_MESSAGE_MANAGEMENT: bool = True
    
    # Cache settings
    CACHE_TIMEOUT: int = 300  # 5 minutes
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that all required settings are present"""
        required_settings = [
            cls.OPENAI_API_KEY,
            cls.TELEGRAM_TOKEN,
            cls.MONGO_URL
        ]
        
        return all(setting for setting in required_settings)
    
    @classmethod
    def get_openai_model(cls, prefer_fallback: bool = False) -> str:
        """Get the appropriate OpenAI model"""
        return cls.OPENAI_MODEL_FALLBACK if prefer_fallback else cls.OPENAI_MODEL_DEFAULT

# Global settings instance
settings = Settings()