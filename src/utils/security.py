"""
Security configuration for the Zendesk Voice Integration Server.
"""

import os
from typing import Dict, Any

class SecurityConfig:
    """Security configuration class."""
    
    # Rate limiting configuration
    RATE_LIMIT_STORAGE_URI = "memory://"
    DEFAULT_RATE_LIMITS = ["100 per hour", "20 per minute"]
    STRICT_RATE_LIMITS = ["50 per hour", "10 per minute"]
    
    # Request size limits (in bytes)
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024  # 1MB
    
    # Security headers
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'",
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'
    }
    
    # Input validation patterns
    PHONE_NUMBER_PATTERN = r'^\+\d{10,15}$'
    SUSPICIOUS_PATTERNS = [
        r'<script',
        r'javascript:',
        r'data:',
        r'vbscript:',
        r'onload=',
        r'onerror=',
        r'eval\(',
        r'expression\(',
        r'SELECT.*FROM',
        r'INSERT.*INTO',
        r'UPDATE.*SET',
        r'DELETE.*FROM'
    ]
    
    # Logging configuration
    LOG_SANITIZATION_FIELDS = ['phone', 'email', 'name', 'password', 'token']
    
    @staticmethod
    def get_config() -> Dict[str, Any]:
        """Get security configuration based on environment."""
        env = os.getenv('FLASK_ENV', 'production')
        
        config = {
            'DEBUG': env == 'development',
            'TESTING': False,
            'SECRET_KEY': os.getenv('SECRET_KEY', os.urandom(32)),
            'MAX_CONTENT_LENGTH': SecurityConfig.MAX_CONTENT_LENGTH,
            'SECURITY_HEADERS': SecurityConfig.SECURITY_HEADERS.copy()
        }
        
        # Production-specific settings
        if env == 'production':
            config.update({
                'SESSION_COOKIE_SECURE': True,
                'SESSION_COOKIE_HTTPONLY': True,
                'SESSION_COOKIE_SAMESITE': 'Strict',
                'PERMANENT_SESSION_LIFETIME': 3600,  # 1 hour
            })
        
        return config
