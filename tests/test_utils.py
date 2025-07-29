"""
Tests for the utility helper functions.
"""

import unittest
import sys
import os
from datetime import datetime

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.helpers import (
    clean_phone_number,
    format_call_description,
    validate_phone_number,
    extract_call_summary,
    create_ticket_subject,
    sanitize_tags,
    format_timestamp
)


class TestHelperFunctions(unittest.TestCase):
    """Test cases for the helper utility functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_call_data = {
            "call": {
                "call_id": "test_call_123",
                "from_number": "+15551234567",
                "call_status": "ended",
                "start_timestamp": 1640995200000,  # 2022-01-01 00:00:00 UTC
                "end_timestamp": 1640995260000,    # 2022-01-01 00:01:00 UTC
                "duration_ms": 60000,
                "transcript": "User: Hello\nAgent: Hi, how can I help you?",
                "call_analysis": {
                    "call_summary": "Customer called for support",
                    "custom_analysis_data": {
                        "name_of_caller": "John Doe",
                        "email_to_reach": "john@example.com"
                    }
                }
            }
        }
    
    def test_clean_phone_number(self):
        """Test phone number cleaning functionality."""
        test_cases = [
            ("+1-555-123-4567", "15551234567"),
            ("(555) 123-4567", "5551234567"),
            ("555.123.4567", "5551234567"),
            ("5551234567", "5551234567"),
            ("+1 555 123 4567", "15551234567"),
            ("555-123-4567", "5551234567"),
            ("555 123 4567", "5551234567"),
            ("", ""),
            ("abc123def", "123"),
            ("+44 20 7946 0958", "442079460958")
        ]
        
        for input_phone, expected in test_cases:
            with self.subTest(input_phone=input_phone):
                result = clean_phone_number(input_phone)
                self.assertEqual(result, expected)
    
    def test_validate_phone_number(self):
        """Test phone number validation."""
        # Valid phone numbers
        valid_numbers = [
            "+15551234567",
            "5551234567",
            "+44 20 7946 0958",
            "1234567890"
        ]
        
        for phone in valid_numbers:
            with self.subTest(phone=phone):
                self.assertTrue(validate_phone_number(phone))
        
        # Invalid phone numbers
        invalid_numbers = [
            "",
            "123",
            "12345678901234567890",  # Too long
            "abc",
            None
        ]
        
        for phone in invalid_numbers:
            with self.subTest(phone=phone):
                self.assertFalse(validate_phone_number(phone))
    
    def test_format_call_description(self):
        """Test call description formatting."""
        result = format_call_description(self.sample_call_data)
        
        # Check that all required information is present
        self.assertIn("Call ID: test_call_123", result)
        self.assertIn("From: +15551234567", result)
        self.assertIn("Status: ended", result)
        self.assertIn("Customer called for support", result)
        self.assertIn("User: Hello", result)
        self.assertIn("Agent: Hi, how can I help you?", result)
        self.assertIn("Duration: 60.0 seconds", result)
    
    def test_format_call_description_missing_data(self):
        """Test call description formatting with missing data."""
        incomplete_data = {
            "call": {
                "call_id": "test_call_123"
                # Missing other fields
            }
        }
        
        result = format_call_description(incomplete_data)
        
        # Should handle missing data gracefully
        self.assertIn("Call ID: test_call_123", result)
        self.assertIn("From: Unknown", result)
        self.assertIn("Status: Unknown", result)
    
    def test_extract_call_summary(self):
        """Test call summary extraction."""
        # Test with call summary
        result = extract_call_summary(self.sample_call_data)
        self.assertEqual(result, "Customer called for support")
        
        # Test with long summary
        long_summary_data = self.sample_call_data.copy()
        long_summary_data['call']['call_analysis']['call_summary'] = "A" * 150
        result = extract_call_summary(long_summary_data)
        self.assertTrue(result.endswith("..."))
        self.assertEqual(len(result), 100)
        
        # Test with no summary, fallback to transcript
        no_summary_data = self.sample_call_data.copy()
        del no_summary_data['call']['call_analysis']['call_summary']
        result = extract_call_summary(no_summary_data)
        self.assertIn("User: Hello", result)
        
        # Test with no transcript
        no_transcript_data = self.sample_call_data.copy()
        del no_transcript_data['call']['transcript']
        del no_transcript_data['call']['call_analysis']['call_summary']
        result = extract_call_summary(no_transcript_data)
        self.assertEqual(result, "No summary available")
    
    def test_create_ticket_subject(self):
        """Test ticket subject creation."""
        # Test with normal summary
        result = create_ticket_subject("+15551234567", "Customer called for support")
        self.assertEqual(result, "Voice Call - +15551234567 - Customer called for support")
        
        # Test with long summary
        long_summary = "A" * 100
        result = create_ticket_subject("+15551234567", long_summary)
        self.assertTrue(result.endswith("..."))
        self.assertIn("Voice Call - +15551234567", result)
        
        # Test with no summary
        result = create_ticket_subject("+15551234567", "")
        self.assertEqual(result, "Voice Call - +15551234567 - Voice Call")
        
        # Test with different phone formats
        result = create_ticket_subject("5551234567", "Test")
        self.assertEqual(result, "Voice Call - +5551234567 - Test")
    
    def test_sanitize_tags(self):
        """Test tag sanitization."""
        # Test normal tags
        tags = ["voice-call", "test", "support"]
        result = sanitize_tags(tags)
        self.assertEqual(result, ["voice-call", "test", "support"])
        
        # Test tags with special characters
        tags = ["voice_call", "test@123", "support-123", "invalid tag"]
        result = sanitize_tags(tags)
        self.assertEqual(result, ["voice_call", "test123", "support-123", "invalidtag"])
        
        # Test empty and invalid tags
        tags = ["", None, "valid", "a" * 60]  # Too long
        result = sanitize_tags(tags)
        self.assertEqual(result, ["valid"])
        
        # Test empty list
        result = sanitize_tags([])
        self.assertEqual(result, [])
        
        # Test None
        result = sanitize_tags(None)
        self.assertEqual(result, [])
    
    def test_format_timestamp(self):
        """Test timestamp formatting."""
        # Test known timestamp
        timestamp_ms = 1640995200000  # 2022-01-01 00:00:00 UTC
        result = format_timestamp(timestamp_ms)
        self.assertEqual(result, "2022-01-01 00:00:00 UTC")
        
        # Test zero timestamp
        result = format_timestamp(0)
        self.assertEqual(result, "1970-01-01 00:00:00 UTC")
        
        # Test negative timestamp
        result = format_timestamp(-1000)
        self.assertEqual(result, "1969-12-31 23:59:59 UTC")


if __name__ == '__main__':
    unittest.main() 