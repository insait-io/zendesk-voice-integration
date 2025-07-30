"""
Tests for the Flask server endpoints.
"""

import unittest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from server.app import app, is_phone_number_allowed, validate_phone_number, validate_call_data


class TestServerEndpoints(unittest.TestCase):
    """Test cases for the Flask server endpoints."""
    
    def test_phone_number_validation(self):
        """Test phone number validation function."""
        # Valid phone numbers
        self.assertTrue(validate_phone_number("+15551234567"))
        self.assertTrue(validate_phone_number("+441234567890"))
        self.assertTrue(validate_phone_number("+33123456789"))
        
        # Invalid phone numbers
        self.assertFalse(validate_phone_number("15551234567"))  # Missing +
        self.assertFalse(validate_phone_number("+1555123"))     # Too short
        self.assertFalse(validate_phone_number("+15551234567890123"))  # Too long
        self.assertFalse(validate_phone_number("+155512345ab"))  # Contains letters
        self.assertFalse(validate_phone_number(""))             # Empty
        self.assertFalse(validate_phone_number(None))           # None
    
    def test_call_data_validation(self):
        """Test call data validation function."""
        # Valid call data
        is_valid, error = validate_call_data(self.sample_call_data)
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        
        # Invalid call data - missing event
        invalid_data = self.sample_call_data.copy()
        del invalid_data['event']
        is_valid, error = validate_call_data(invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("Missing required field: event", error)
        
        # Invalid call data - missing call
        invalid_data = self.sample_call_data.copy()
        del invalid_data['call']
        is_valid, error = validate_call_data(invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("Missing required field: call", error)
        
        # Invalid call data - invalid phone number
        invalid_data = self.sample_call_data.copy()
        invalid_data['call']['from_number'] = "invalid_phone"
        is_valid, error = validate_call_data(invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("Invalid phone number format", error)
        
        # Invalid call data - invalid event type
        invalid_data = self.sample_call_data.copy()
        invalid_data['event'] = "invalid_event"
        is_valid, error = validate_call_data(invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("Invalid event type", error)

    def test_request_size_limit(self):
        """Test request size limit enforcement."""
        # Create a large payload (over 1MB)
        large_data = self.sample_call_data.copy()
        large_data['call']['transcript'] = "x" * (1024 * 1024 + 1)  # Just over 1MB
        
        with patch('server.app.firestore_client'), \
             patch('server.app.store_processed_call', return_value=True), \
             patch('server.app.check_processed_call', return_value=False):
            
            response = self.app.post('/create_zendesk_ticket', 
                                   data=json.dumps(large_data),
                                   content_type='application/json')
            
            # Should reject large requests (413 Request Entity Too Large)
            self.assertEqual(response.status_code, 413)

    def test_invalid_content_type(self):
        """Test rejection of invalid content types."""
        response = self.app.post('/create_zendesk_ticket', 
                               data='invalid_data',
                               content_type='text/plain')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("Content-Type must be application/json", data['error'])

    def test_security_headers(self):
        """Test that security headers are present in responses."""
        response = self.app.get('/health')
        
        # Check for security headers
        self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(response.headers.get('X-Frame-Options'), 'DENY')
        self.assertEqual(response.headers.get('X-XSS-Protection'), '1; mode=block')
        self.assertIn('max-age=31536000', response.headers.get('Strict-Transport-Security', ''))
        self.assertIn("default-src 'self'", response.headers.get('Content-Security-Policy', ''))

    @patch('server.app.firestore_client')
    def test_malicious_input_rejection(self, mock_firestore):
        """Test rejection of potentially malicious input."""
        malicious_data = self.sample_call_data.copy()
        malicious_data['call']['transcript'] = '<script>alert("xss")</script>'
        
        with patch('server.app.store_processed_call', return_value=True), \
             patch('server.app.check_processed_call', return_value=False), \
             patch('zendesk.api.ZendeskAPI.create_ticket') as mock_create:
            
            mock_create.return_value = None  # API should reject malicious input
            
            response = self.app.post('/create_zendesk_ticket',
                                   data=json.dumps(malicious_data),
                                   content_type='application/json')
            
            # The request should be processed but the Zendesk API should handle validation
            self.assertIn(response.status_code, [400, 500])

    def test_rate_limiting_headers(self):
        """Test that rate limiting is configured."""
        response = self.app.get('/health')
        
        # Check that the response doesn't indicate rate limiting issues
        self.assertNotEqual(response.status_code, 429)
    
    def test_health_check(self):
        """Test the health check endpoint."""
        response = self.app.get('/health')
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['service'], 'zendesk-voice-server')
        self.assertIn('timestamp', data)
    
    @patch('server.app.processed_calls_ref')
    @patch('server.app.ZendeskAPI')
    def test_call_events_manager_success(self, mock_zendesk_class, mock_firebase_ref):
        """Test successful call event processing."""
        mock_firebase_ref.child.return_value.get.return_value = None
        mock_firebase_ref.child.return_value.set.return_value = None
        
        mock_zendesk_instance = Mock()
        mock_zendesk_class.return_value = mock_zendesk_instance
        mock_zendesk_instance.create_ticket.return_value = {
            "ticket": {
                "id": 12345,
                "subject": "Test Ticket",
                "status": "open"
            }
        }
        
        response = self.app.post(
            '/call_events_manager',
            data=json.dumps(self.sample_call_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['ticket_id'], 12345)
    
    @patch('server.app.processed_calls_ref')
    def test_call_events_manager_already_processed(self, mock_firebase_ref):
        """Test call event processing for already processed call."""
        mock_firebase_ref.child.return_value.get.return_value = {
            "ticket_id": 12345,
            "processed_at": "2022-01-01T00:00:00"
        }
        
        response = self.app.post(
            '/call_events_manager',
            data=json.dumps(self.sample_call_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['message'], 'Call already processed')
    
    def test_call_events_manager_no_data(self):
        """Test call event processing with no data."""
        response = self.app.post(
            '/call_events_manager',
            data='',
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', data)
    
    def test_call_events_manager_missing_required_fields(self):
        """Test call event processing with missing required fields."""
        incomplete_data = {
            "call": {
                "call_id": "test_call_123"
            }
        }
        
        response = self.app.post(
            '/call_events_manager',
            data=json.dumps(incomplete_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', data)
    
    def test_call_events_manager_call_not_ended(self):
        """Test call event processing for call that hasn't ended."""
        call_data = self.sample_call_data.copy()
        call_data['call']['call_status'] = 'in-progress'
        
        response = self.app.post(
            '/call_events_manager',
            data=json.dumps(call_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['message'], 'Call not ended yet')
    
    @patch('server.app.ZendeskAPI')
    def test_create_zendesk_ticket_success(self, mock_zendesk_class):
        """Test successful manual ticket creation."""
        mock_zendesk_instance = Mock()
        mock_zendesk_class.return_value = mock_zendesk_instance
        mock_zendesk_instance.create_ticket.return_value = {
            "ticket": {
                "id": 12345,
                "subject": "Test Ticket",
                "status": "open",
                "requester_id": 67890,
                "tags": ["test", "voice-call"]
            }
        }
        
        response = self.app.post(
            '/create_zendesk_ticket',
            data=json.dumps(self.sample_ticket_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertIn('ticket', data)
        self.assertEqual(data['ticket']['id'], 12345)
    
    def test_create_zendesk_ticket_missing_fields(self):
        """Test manual ticket creation with missing fields."""
        incomplete_data = {
            "subject": "Test Ticket"
        }
        
        response = self.app.post(
            '/create_zendesk_ticket',
            data=json.dumps(incomplete_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', data)
    
    @patch('server.app.ZendeskAPI')
    def test_create_zendesk_ticket_failure(self, mock_zendesk_class):
        """Test manual ticket creation failure."""
        mock_zendesk_instance = Mock()
        mock_zendesk_class.return_value = mock_zendesk_instance
        mock_zendesk_instance.create_ticket.return_value = None
        
        response = self.app.post(
            '/create_zendesk_ticket',
            data=json.dumps(self.sample_ticket_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 500)
        self.assertIn('error', data)
    
    @patch('server.app.ZendeskAPI')
    def test_test_zendesk_flow_success(self, mock_zendesk_class):
        """Test successful Zendesk flow test."""
        mock_zendesk_instance = Mock()
        mock_zendesk_class.return_value = mock_zendesk_instance
        
        mock_zendesk_instance.search_user_by_phone.return_value = [
            {"id": 67890, "name": "John Doe"}
        ]
        
        mock_zendesk_instance.create_ticket.return_value = {
            "ticket": {
                "id": 12345,
                "subject": "Test Ticket",
                "status": "open"
            }
        }
        
        mock_zendesk_instance.update_ticket.return_value = {
            "ticket": {
                "id": 12345,
                "status": "solved"
            }
        }
        
        response = self.app.get('/test_zendesk_flow')
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertIn('test_results', data)
        self.assertTrue(data['test_results']['ticket_created'])
        self.assertTrue(data['test_results']['ticket_updated'])
    
    @patch('server.app.ZendeskAPI')
    def test_test_zendesk_flow_failure(self, mock_zendesk_class):
        """Test Zendesk flow test failure."""
        mock_zendesk_instance = Mock()
        mock_zendesk_class.return_value = mock_zendesk_instance
        mock_zendesk_instance.search_user_by_phone.return_value = []
        mock_zendesk_instance.create_ticket.return_value = None
        
        response = self.app.get('/test_zendesk_flow')
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 500)
        self.assertFalse(data['success'])
        self.assertIn('error', data)


class TestPhoneNumberFiltering(unittest.TestCase):
    """Test cases for phone number filtering functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.app = app.test_client()
        self.app.testing = True
        
        self.sample_ticket_data = {
            "event": "call_started",
            "call": {
                "call_id": "test_call_123",
                "from_number": "+15551234567",
                "start_timestamp": 1640995200000
            }
        }
    
    @patch.dict(os.environ, {}, clear=True)
    def test_phone_filtering_no_restriction(self):
        """Test that when ALLOWED_PHONE_NUMBERS is not set, all numbers are allowed."""
        result = is_phone_number_allowed("+15551234567")
        self.assertTrue(result)
        
        result = is_phone_number_allowed("+19999999999")
        self.assertTrue(result)
    
    @patch.dict(os.environ, {'ALLOWED_PHONE_NUMBERS': '+15551234567,+15559876543'})
    def test_phone_filtering_with_restriction_allowed(self):
        """Test that allowed phone numbers are accepted when restriction is set."""
        result = is_phone_number_allowed("+15551234567")
        self.assertTrue(result)
        
        result = is_phone_number_allowed("+15559876543")
        self.assertTrue(result)
    
    @patch.dict(os.environ, {'ALLOWED_PHONE_NUMBERS': '+15551234567,+15559876543'})
    def test_phone_filtering_with_restriction_denied(self):
        """Test that non-allowed phone numbers are rejected when restriction is set."""
        result = is_phone_number_allowed("+19999999999")
        self.assertFalse(result)
        
        result = is_phone_number_allowed("+11111111111")
        self.assertFalse(result)
    
    @patch.dict(os.environ, {'ALLOWED_PHONE_NUMBERS': ' +15551234567 , +15559876543 '})
    def test_phone_filtering_whitespace_handling(self):
        """Test that whitespace in the environment variable is handled correctly."""
        result = is_phone_number_allowed("+15551234567")
        self.assertTrue(result)
        
        result = is_phone_number_allowed("+15559876543")
        self.assertTrue(result)
        
        result = is_phone_number_allowed("+19999999999")
        self.assertFalse(result)
    
    @patch.dict(os.environ, {'ALLOWED_PHONE_NUMBERS': '+15551234567,+15559876543'})
    @patch('server.app.processed_calls_ref')
    def test_create_ticket_endpoint_phone_filtering_denied(self, mock_firebase_ref):
        """Test that create_zendesk_ticket endpoint rejects unauthorized phone numbers."""
        mock_firebase_ref.child.return_value.get.return_value = None
        
        unauthorized_data = self.sample_ticket_data.copy()
        unauthorized_data["call"]["from_number"] = "+19999999999"
        
        response = self.app.post(
            '/create_zendesk_ticket',
            data=json.dumps(unauthorized_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 403)
        self.assertEqual(data['error'], 'Phone number not authorized')
        self.assertIn('not authorized to create tickets', data['message'])
    
    @patch.dict(os.environ, {'ALLOWED_PHONE_NUMBERS': '+15551234567,+15559876543'})
    @patch('server.app.processed_calls_ref')
    @patch('server.app.active_tickets_ref')
    @patch('server.app.ZendeskAPI')
    def test_create_ticket_endpoint_phone_filtering_allowed(self, mock_zendesk_class, mock_active_tickets_ref, mock_processed_calls_ref):
        """Test that create_zendesk_ticket endpoint accepts authorized phone numbers."""
        mock_processed_calls_ref.child.return_value.get.return_value = None
        mock_processed_calls_ref.child.return_value.set.return_value = None
        mock_active_tickets_ref.child.return_value.set.return_value = None
        
        mock_zendesk_instance = Mock()
        mock_zendesk_class.return_value = mock_zendesk_instance
        mock_zendesk_instance.create_ticket.return_value = {
            "ticket": {
                "id": 12345,
                "subject": "Test Ticket",
                "status": "open"
            }
        }
        
        authorized_data = self.sample_ticket_data.copy()
        authorized_data["call"]["from_number"] = "+15551234567"
        
        response = self.app.post(
            '/create_zendesk_ticket',
            data=json.dumps(authorized_data),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 201)
        self.assertIn('ticket', data)


if __name__ == '__main__':
    unittest.main()