"""
Configuration settings for the Zendesk Voice Server.
"""

import os
from typing import Optional


class Config:
    """Base configuration class."""
    
    # Zendesk settings
    ZENDESK_DOMAIN = os.getenv('ZENDESK_DOMAIN', '')
    ZENDESK_EMAIL = os.getenv('ZENDESK_EMAIL', '')
    ZENDESK_API_TOKEN = os.getenv('ZENDESK_API_TOKEN', '')
    
    # Firebase settings
    FIREBASE_CREDENTIALS_FILE = os.getenv('FIREBASE_CREDENTIALS_FILE', 'firebase-credentials.json')
    FIREBASE_DATABASE_URL = os.getenv('FIREBASE_DATABASE_URL', '')
    
    # Server settings
    PORT = int(os.getenv('PORT', 5000))
    
    # Phone number filtering
    ALLOWED_PHONE_NUMBERS = os.getenv('ALLOWED_PHONE_NUMBERS')


class DevelopmentConfig(Config):
    """Development configuration."""
    pass


class ProductionConfig(Config):
    """Production configuration."""
    pass


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    
    # Use test credentials
    ZENDESK_DOMAIN = 'test.zendesk.com'
    ZENDESK_EMAIL = 'test@example.com'
    ZENDESK_API_TOKEN = 'test-token'


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name: Optional[str] = None) -> Config:
    """
    Get configuration class based on environment.
    
    Args:
        config_name: Name of the configuration to use
        
    Returns:
        Configuration class instance
    """
    if config_name is None:
        config_name = os.getenv('ENVIRONMENT', 'default')
    
    return config.get(config_name, config['default']) 