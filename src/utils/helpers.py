"""
Helper utilities for the Zendesk voice server.
"""

import re
from datetime import datetime
from typing import Dict, Any, Optional


def clean_phone_number(phone_number: str) -> str:
    """
    Clean a phone number by removing non-numeric characters.
    
    Args:
        phone_number: Raw phone number string
        
    Returns:
        Cleaned phone number with only digits
    """
    return ''.join(filter(str.isdigit, phone_number.replace('+', '')))


def format_call_description(call_data: Dict[str, Any]) -> str:
    """
    Format call data into a readable description for Zendesk tickets.
    
    Args:
        call_data: Dictionary containing call information
        
    Returns:
        Formatted description string
    """
    call = call_data.get('call', {})
    call_analysis = call.get('call_analysis', {})
    
    # Extract basic call info
    call_id = call.get('call_id', 'Unknown')
    from_number = call.get('from_number', 'Unknown')
    call_status = call.get('call_status', 'Unknown')
    summary = call_analysis.get('call_summary', 'No summary available')
    transcript = call.get('transcript', 'No transcript available')
    
    # Format timestamps
    start_time = datetime.fromtimestamp(call.get('start_timestamp', 0) / 1000)
    end_time = datetime.fromtimestamp(call.get('end_timestamp', 0) / 1000)
    duration = call.get('duration_ms', 0) / 1000
    
    description = f"""
Call Information:
- Call ID: {call_id}
- From: {from_number}
- Status: {call_status}
- Summary: {summary}

Call Details:
- Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}
- End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}
- Duration: {duration:.1f} seconds

Transcript:
{transcript}
"""
    
    return description.strip()


def validate_phone_number(phone_number: str) -> bool:
    """
    Validate if a phone number is in a reasonable format.
    
    Args:
        phone_number: Phone number to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not phone_number:
        return False
    
    # Remove common formatting characters
    cleaned = clean_phone_number(phone_number)
    
    # Check if it's a reasonable length (7-15 digits)
    return 7 <= len(cleaned) <= 15


def extract_call_summary(call_data: Dict[str, Any]) -> str:
    """
    Extract a concise summary from call data.
    
    Args:
        call_data: Dictionary containing call information
        
    Returns:
        Concise summary string
    """
    call = call_data.get('call', {})
    call_analysis = call.get('call_analysis', {})
    
    # Try to get the call summary
    summary = call_analysis.get('call_summary', '')
    
    if summary:
        # Truncate if too long
        if len(summary) > 100:
            summary = summary[:97] + "..."
        return summary
    
    # Fallback: create summary from transcript
    transcript = call.get('transcript', '')
    if transcript:
        # Take first 100 characters of transcript
        return transcript[:100] + "..." if len(transcript) > 100 else transcript
    
    return "No summary available"


def create_ticket_subject(from_number: str, summary: str) -> str:
    """
    Create a subject line for a Zendesk ticket.
    
    Args:
        from_number: Phone number of the caller
        summary: Call summary or description
        
    Returns:
        Formatted subject string
    """
    # Clean the phone number for display
    clean_number = clean_phone_number(from_number)
    display_number = f"+{clean_number}" if len(clean_number) == 10 else from_number
    
    # Create subject with summary
    if summary and len(summary) > 50:
        summary_part = summary[:47] + "..."
    else:
        summary_part = summary or "Voice Call"
    
    return f"Voice Call - {display_number} - {summary_part}"


def sanitize_tags(tags: list) -> list:
    """
    Sanitize and validate tags for Zendesk.
    
    Args:
        tags: List of tags to sanitize
        
    Returns:
        List of sanitized tags
    """
    if not tags:
        return []
    
    sanitized = []
    for tag in tags:
        if tag and isinstance(tag, str):
            # Remove special characters that might cause issues
            clean_tag = re.sub(r'[^\w\-_]', '', tag.lower())
            if clean_tag and len(clean_tag) <= 50:  # Zendesk tag length limit
                sanitized.append(clean_tag)
    
    return sanitized


def format_timestamp(timestamp_ms: int) -> str:
    """
    Format a millisecond timestamp to a readable string.
    
    Args:
        timestamp_ms: Timestamp in milliseconds
        
    Returns:
        Formatted datetime string
    """
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S UTC') 