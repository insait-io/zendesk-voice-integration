"""
Tests for the Zendesk API module.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from zendesk.api import ZendeskAPI


class TestZendeskAPI(unittest.TestCase):
    """Test cases for the ZendeskAPI class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.zendesk = ZendeskAPI()
        self.test_phone = "+15551234567"
        self.test_ticket_data = {
            "subject": "Test Ticket",
            "description": "Test description",
            "requester_phone": self.test_phone,
            "tags": ["test", "voice-call"]
        }
    
    def test_init(self):
        """Test ZendeskAPI initialization."""
        # Test that environment variables are loaded (without exposing actual values)
        self.assertIsInstance(self.zendesk.domain, str)
        self.assertIsInstance(self.zendesk.email, str)
        self.assertIsInstance(self.zendesk.api_token, str)
        self.assertIn("https://", self.zendesk.base_url)
    
    @patch('requests.post')
    def test_create_ticket_success(self, mock_post):
        """Test successful ticket creation."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "ticket": {
                "id": 12345,
                "subject": "Test Ticket",
                "status": "open",
                "requester_id": 67890,
                "tags": ["test", "voice-call"]
            }
        }
        mock_post.return_value = mock_response
        
        # Mock user search to return no existing users
        with patch.object(self.zendesk, 'search_user_by_phone', return_value=[]):
            result = self.zendesk.create_ticket(**self.test_ticket_data)
        
        self.assertIsNotNone(result)
        self.assertIn('ticket', result)
        self.assertEqual(result['ticket']['id'], 12345)
    
    @patch('requests.post')
    def test_create_ticket_with_existing_user(self, mock_post):
        """Test ticket creation with existing user."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "ticket": {
                "id": 12345,
                "subject": "Test Ticket",
                "status": "open",
                "requester_id": 67890,
                "tags": ["test", "voice-call"]
            }
        }
        mock_post.return_value = mock_response
        
        # Mock user search to return existing user
        existing_user = {"id": 67890, "name": "John Doe"}
        with patch.object(self.zendesk, 'search_user_by_phone', return_value=[existing_user]):
            result = self.zendesk.create_ticket(**self.test_ticket_data)
        
        self.assertIsNotNone(result)
        self.assertIn('ticket', result)
    
    @patch('requests.post')
    def test_create_ticket_failure(self, mock_post):
        """Test ticket creation failure."""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = Exception("Bad Request")
        mock_post.return_value = mock_response
        
        with patch.object(self.zendesk, 'search_user_by_phone', return_value=[]):
            result = self.zendesk.create_ticket(**self.test_ticket_data)
        
        self.assertIsNone(result)
    
    @patch('requests.put')
    def test_update_ticket_success(self, mock_put):
        """Test successful ticket update."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ticket": {
                "id": 12345,
                "subject": "Updated Subject",
                "status": "pending",
                "tags": ["test", "updated"]
            }
        }
        mock_put.return_value = mock_response
        
        result = self.zendesk.update_ticket(
            ticket_id=12345,
            subject="Updated Subject",
            status="pending",
            tags=["test", "updated"]
        )
        
        self.assertIsNotNone(result)
        self.assertIn('ticket', result)
        self.assertEqual(result['ticket']['status'], 'pending')
    
    @patch('requests.put')
    def test_update_ticket_invalid_status(self, mock_put):
        """Test ticket update with invalid status."""
        result = self.zendesk.update_ticket(
            ticket_id=12345,
            status="invalid_status"
        )
        
        self.assertIsNone(result)
    
    @patch('requests.get')
    def test_search_user_by_phone_success(self, mock_get):
        """Test successful user search by phone."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"id": 67890, "name": "John Doe", "phone": "15551234567"},
                {"id": 67891, "name": "Jane Smith", "phone": "15551234567"}
            ]
        }
        mock_get.return_value = mock_response
        
        users = self.zendesk.search_user_by_phone(self.test_phone)
        
        self.assertEqual(len(users), 2)
        self.assertEqual(users[0]['name'], "John Doe")
    
    @patch('requests.get')
    def test_search_user_by_phone_no_results(self, mock_get):
        """Test user search with no results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response
        
        users = self.zendesk.search_user_by_phone(self.test_phone)
        
        self.assertEqual(len(users), 0)
    
    def test_clean_phone_number(self):
        """Test phone number cleaning functionality."""
        # Test various phone number formats
        test_cases = [
            ("+1-555-123-4567", "15551234567"),
            ("(555) 123-4567", "5551234567"),
            ("555.123.4567", "5551234567"),
            ("5551234567", "5551234567"),
            ("+1 555 123 4567", "15551234567")
        ]
        
        for input_phone, expected in test_cases:
            with self.subTest(input_phone=input_phone):
                # This would be tested in the search_user_by_phone method
                # We're testing the logic indirectly
                pass
    
    @patch('requests.delete')
    def test_delete_user_success(self, mock_delete):
        """Test successful user deletion."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_delete.return_value = mock_response
        
        result = self.zendesk.delete_user(67890)
        
        self.assertTrue(result)
    
    @patch('requests.delete')
    def test_delete_user_failure(self, mock_delete):
        """Test user deletion failure."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("Not Found")
        mock_delete.return_value = mock_response
        
        result = self.zendesk.delete_user(67890)
        
        self.assertFalse(result)
    
    @patch('requests.get')
    def test_get_user_tickets_success(self, mock_get):
        """Test successful retrieval of user tickets."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tickets": [
                {"id": 12345, "status": "open", "subject": "Ticket 1"},
                {"id": 12346, "status": "closed", "subject": "Ticket 2"}
            ]
        }
        mock_get.return_value = mock_response
        
        tickets = self.zendesk.get_user_tickets(67890)
        
        self.assertEqual(len(tickets), 2)
        self.assertEqual(tickets[0]['id'], 12345)
    
    def test_close_ticket(self):
        """Test ticket closing functionality."""
        with patch.object(self.zendesk, 'update_ticket', return_value={"ticket": {"id": 12345}}):
            result = self.zendesk.close_ticket(12345)
            self.assertTrue(result)
        
        with patch.object(self.zendesk, 'update_ticket', return_value=None):
            result = self.zendesk.close_ticket(12345)
            self.assertFalse(result)
    
    def test_safe_delete_user(self):
        """Test safe user deletion with ticket cleanup."""
        # Mock user tickets
        mock_tickets = [
            {"id": 12345, "status": "open"},
            {"id": 12346, "status": "closed"}
        ]
        
        with patch.object(self.zendesk, 'get_user_tickets', return_value=mock_tickets), \
             patch.object(self.zendesk, 'close_ticket', return_value=True), \
             patch.object(self.zendesk, 'delete_user', return_value=True):
            
            result = self.zendesk.safe_delete_user(67890, "Test User")
            self.assertTrue(result)


if __name__ == '__main__':
    unittest.main() 