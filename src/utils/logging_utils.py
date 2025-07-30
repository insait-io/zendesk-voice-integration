"""
Secure logging utilities to prevent log injection attacks.
"""

import re
import logging
from typing import Any


def sanitize_for_logging(value: Any) -> str:
    """
    Sanitize a value for safe logging to prevent CRLF injection attacks.
    
    Args:
        value: The value to sanitize
        
    Returns:
        Sanitized string safe for logging
    """
    if value is None:
        return "None"
    
    # Convert to string
    log_value = str(value)
    
    # Remove or replace dangerous characters
    # Remove carriage return and line feed characters
    log_value = re.sub(r'[\r\n]+', ' ', log_value)
    
    # Remove other control characters except space and tab
    log_value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', log_value)
    
    # Limit length to prevent log flooding
    if len(log_value) > 500:
        log_value = log_value[:497] + "..."
    
    return log_value


def safe_log_info(message: str, *args, **kwargs):
    """
    Safely log an info message with sanitized arguments.
    
    Args:
        message: Log message format string
        *args: Positional arguments to format into message
        **kwargs: Keyword arguments
    """
    sanitized_args = [sanitize_for_logging(arg) for arg in args]
    safe_message = sanitize_for_logging(message)
    
    try:
        formatted_message = safe_message % tuple(sanitized_args) if sanitized_args else safe_message
        logging.info(formatted_message, **kwargs)
    except (TypeError, ValueError):
        # Fallback if formatting fails
        logging.info(f"[LOG_FORMAT_ERROR] {safe_message}", **kwargs)


def safe_log_warning(message: str, *args, **kwargs):
    """
    Safely log a warning message with sanitized arguments.
    
    Args:
        message: Log message format string
        *args: Positional arguments to format into message
        **kwargs: Keyword arguments
    """
    sanitized_args = [sanitize_for_logging(arg) for arg in args]
    safe_message = sanitize_for_logging(message)
    
    try:
        formatted_message = safe_message % tuple(sanitized_args) if sanitized_args else safe_message
        logging.warning(formatted_message, **kwargs)
    except (TypeError, ValueError):
        # Fallback if formatting fails
        logging.warning(f"[LOG_FORMAT_ERROR] {safe_message}", **kwargs)


def safe_log_error(message: str, *args, **kwargs):
    """
    Safely log an error message with sanitized arguments.
    
    Args:
        message: Log message format string
        *args: Positional arguments to format into message
        **kwargs: Keyword arguments
    """
    sanitized_args = [sanitize_for_logging(arg) for arg in args]
    safe_message = sanitize_for_logging(message)
    
    try:
        formatted_message = safe_message % tuple(sanitized_args) if sanitized_args else safe_message
        logging.error(formatted_message, **kwargs)
    except (TypeError, ValueError):
        # Fallback if formatting fails
        logging.error(f"[LOG_FORMAT_ERROR] {safe_message}", **kwargs)


def safe_log_debug(message: str, *args, **kwargs):
    """
    Safely log a debug message with sanitized arguments.
    
    Args:
        message: Log message format string
        *args: Positional arguments to format into message
        **kwargs: Keyword arguments
    """
    sanitized_args = [sanitize_for_logging(arg) for arg in args]
    safe_message = sanitize_for_logging(message)
    
    try:
        formatted_message = safe_message % tuple(sanitized_args) if sanitized_args else safe_message
        logging.debug(formatted_message, **kwargs)
    except (TypeError, ValueError):
        # Fallback if formatting fails
        logging.debug(f"[LOG_FORMAT_ERROR] {safe_message}", **kwargs)
