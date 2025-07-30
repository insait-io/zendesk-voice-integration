import os
import requests
import logging
import time
import re
import sys
from typing import List, Optional, Dict, Any
from urllib.parse import quote

# Add the src directory to the Python path for relative imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.utils.logging_utils import sanitize_for_logging, safe_log_info, safe_log_warning, safe_log_error, safe_log_debug

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Disable debug logging in production
if os.getenv('FLASK_ENV') != 'development':
    logging.getLogger().setLevel(logging.WARNING)

# Constants
USER_AGENT = "Insait-Voice-Integration/2.0"

class ZendeskAPI:
    """
    Zendesk API client for voice call integration.
    
    This class provides methods to interact with the Zendesk API for creating
    and managing tickets related to voice calls.
    """
    
    def __init__(self):
        self.domain = os.getenv('ZENDESK_DOMAIN', '').strip()
        self.email = os.getenv('ZENDESK_EMAIL', '').strip()
        self.api_token = os.getenv('ZENDESK_API_TOKEN', '').strip()
        
        # Validate required environment variables
        if not all([self.domain, self.email, self.api_token]):
            raise ValueError("Missing required Zendesk configuration: ZENDESK_DOMAIN, ZENDESK_EMAIL, or ZENDESK_API_TOKEN")
        
        # Validate domain format
        if not re.match(r'^[a-zA-Z0-9-]+\.zendesk\.com$', self.domain):
            raise ValueError("Invalid Zendesk domain format. Should be like 'yourcompany.zendesk.com'")
        
        # Ensure HTTPS
        self.base_url = f"https://{self.domain}/api/v2"
        
        # Configure session with timeout and retry
        self.session = requests.Session()
        self.session.timeout = 30
        
        safe_log_info(f"Initialized ZendeskAPI with domain: {self._sanitize_domain(self.domain)}")

    def _sanitize_domain(self, domain):
        """Sanitize domain for logging."""
        if len(domain) > 10:
            return domain[:5] + "*" * (len(domain) - 10) + domain[-5:]
        return "*" * len(domain)

    def _sanitize_for_logging(self, data):
        """Sanitize sensitive data for logging."""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if key.lower() in ['phone', 'email', 'name']:
                    sanitized[key] = "***REDACTED***"
                else:
                    sanitized[key] = value
            return sanitized
        return data

    def _validate_input(self, data):
        """Validate input data for security."""
        if isinstance(data, str):
            # Check for potential injection attempts
            suspicious_patterns = [
                r'<script',
                r'javascript:',
                r'data:',
                r'vbscript:',
                r'onload=',
                r'onerror=',
                r'eval\(',
                r'expression\(',
            ]
            
            for pattern in suspicious_patterns:
                if re.search(pattern, data, re.IGNORECASE):
                    raise ValueError("Potentially malicious content detected")
        
        return True

    def _validate_ticket_inputs(self, subject: str, description: str, tags: List[str], requester_phone: str) -> bool:
        """Validate all inputs for ticket creation."""
        try:
            self._validate_input(subject)
            self._validate_input(description)
            for tag in tags:
                self._validate_input(tag)
        except ValueError as e:
            safe_log_error(f"Input validation failed: {sanitize_for_logging(str(e))}")
            return False
        
        # Validate phone number format
        if not re.match(r'^\+\d{10,15}$', requester_phone):
            safe_log_error("Invalid phone number format")
            return False
        
        return True
    
    def _select_best_user(self, users: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select the most appropriate user from search results."""
        if not users:
            return None
        
        # First try to find a user with a name other than 'Customer'
        named_users = [u for u in users if u.get('name') and u.get('name').lower() != 'customer']
        if named_users:
            selected_user = named_users[0]
            safe_log_info(f"Selected named user (ID: {sanitize_for_logging(str(selected_user.get('id', 'N/A')))})")
            return selected_user
        else:
            # If no named users found, use the first user
            selected_user = users[0]
            safe_log_info(f"Selected first available user (ID: {sanitize_for_logging(str(selected_user.get('id', 'N/A')))})")
            return selected_user
    
    def _prepare_ticket_data(self, subject: str, description: str, tags: List[str], 
                           requester_phone: str, selected_user: Optional[Dict[str, Any]], 
                           public: bool) -> Dict[str, Any]:
        """Prepare ticket data structure for API request."""
        data = {
            "ticket": {
                "subject": subject[:255],  # Limit subject length
                "comment": {
                    "body": description[:65535],  # Limit description length
                    "public": public
                },
                "tags": tags[:10]  # Limit number of tags
            }
        }

        # If we found an existing user, use their ID
        if selected_user:
            data["ticket"]["requester_id"] = selected_user.get('id')
            safe_log_info(f"Creating ticket for existing user ID: {sanitize_for_logging(str(selected_user.get('id', 'N/A')))}")
        else:
            # Only create a new user if we didn't find any existing ones
            safe_log_info("No existing user found, creating ticket with new user")
            data["ticket"]["requester"] = {
                "phone": requester_phone,
                "name": "New Caller - Insait AI Agent"  # Default name for new users
            }
        
        return data
    
    def _make_ticket_request(self, url: str, data: Dict[str, Any]) -> Optional[dict]:
        """Make the actual API request to create the ticket."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT
        }
        
        sanitized_data = self._sanitize_for_logging(data)
        safe_log_debug(f"Request payload: {sanitize_for_logging(str(sanitized_data))}")
        
        try:
            safe_log_info(f"Sending request to Zendesk API: {sanitize_for_logging(url)}")
            response = self.session.post(
                url,
                auth=(f"{self.email}/token", self.api_token),
                headers=headers,
                json=data,
                timeout=30
            )
            safe_log_info(f"Zendesk API response status code: {sanitize_for_logging(str(response.status_code))}")
            
            response.raise_for_status()
            response_data = response.json()
            safe_log_info(f"Successfully created Zendesk ticket with ID: {sanitize_for_logging(str(response_data.get('ticket', {}).get('id', 'N/A')))}")
            return response_data
        except requests.exceptions.Timeout:
            safe_log_error("Request to Zendesk API timed out")
            return None
        except requests.exceptions.RequestException as e:
            safe_log_error(f"Error creating Zendesk ticket: {sanitize_for_logging(str(e))}")
            if hasattr(e, 'response') and e.response is not None:
                safe_log_error(f"Error response status: {sanitize_for_logging(str(e.response.status_code))}")
                if e.response.status_code < 500:  # Don't log server errors content
                    safe_log_error(f"Error response body: {sanitize_for_logging(e.response.text[:1000])}")
            return None

    def create_ticket(
        self,
        subject: str,
        description: str,
        requester_phone: str,
        tags: List[str],
        public: bool = False
    ) -> Optional[dict]:
        """
        Create a new Zendesk ticket
        
        Args:
            subject: Ticket subject
            description: Ticket description/body
            requester_phone: Phone number of the requester
            tags: List of tags to apply to the ticket
            public: Whether the comment should be public (default: False)
            
        Returns:
            dict: Response from Zendesk API if successful, None if failed
        """
        url = f"{self.base_url}/tickets.json"
        
        # Validate inputs
        if not self._validate_ticket_inputs(subject, description, tags, requester_phone):
            return None
        
        safe_log_info("Creating Zendesk ticket")
        safe_log_debug(f"Ticket subject: {sanitize_for_logging(subject)}")
        safe_log_debug(f"Ticket tags: {sanitize_for_logging(str(tags))}")
        
        # Look up user by phone number and select the best match
        users = self.search_user_by_phone(requester_phone)
        selected_user = self._select_best_user(users)
        
        # Prepare the ticket data
        data = self._prepare_ticket_data(subject, description, tags, requester_phone, selected_user, public)
        
        # Make the API request
        return self._make_ticket_request(url, data)

    def _validate_update_inputs(self, subject: Optional[str], description: Optional[str], 
                              tags: Optional[List[str]], status: Optional[str]) -> bool:
        """Validate inputs for ticket update."""
        if subject is not None:
            try:
                self._validate_input(subject)
            except ValueError as e:
                safe_log_error(f"Subject validation failed: {sanitize_for_logging(str(e))}")
                return False
            
        if description is not None:
            try:
                self._validate_input(description)
            except ValueError as e:
                safe_log_error(f"Description validation failed: {sanitize_for_logging(str(e))}")
                return False
            
        if tags is not None:
            for tag in tags:
                try:
                    self._validate_input(tag)
                except ValueError as e:
                    safe_log_error(f"Tag validation failed: {sanitize_for_logging(str(e))}")
                    return False
            
        if status is not None:
            valid_statuses = ['open', 'pending', 'solved', 'closed']
            if status.lower() not in valid_statuses:
                safe_log_error(f"Invalid status '{sanitize_for_logging(status)}'. Must be one of: {sanitize_for_logging(str(valid_statuses))}")
                return False
        
        return True
    
    def _prepare_update_data(self, subject: Optional[str], description: Optional[str], 
                           tags: Optional[List[str]], status: Optional[str], public: bool) -> Dict[str, Any]:
        """Prepare update data structure for API request."""
        data = {"ticket": {}}
        
        if subject is not None:
            data["ticket"]["subject"] = subject[:255]  # Limit subject length
            safe_log_debug("Updating ticket subject")
            
        if description is not None:
            # For updates, comments must be added to a separate comment field
            data["ticket"]["comment"] = {
                "body": description[:65535],  # Limit description length
                "public": public
            }
            safe_log_debug("Adding new comment to ticket")
            
        if tags is not None:
            data["ticket"]["tags"] = tags[:10]  # Limit number of tags
            safe_log_debug("Updating ticket tags")
            
        if status is not None:
            data["ticket"]["status"] = status.lower()
            safe_log_debug(f"Updating ticket status: {sanitize_for_logging(status)}")
        
        return data
    
    def _make_update_request(self, url: str, data: Dict[str, Any], ticket_id: int) -> Optional[dict]:
        """Make the actual API request to update the ticket."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT
        }
        
        sanitized_data = self._sanitize_for_logging(data)
        safe_log_debug(f"Request payload: {sanitize_for_logging(str(sanitized_data))}")
        
        try:
            safe_log_info(f"Sending PUT request to Zendesk API: {sanitize_for_logging(url)}")
            response = self.session.put(
                url,
                auth=(f"{self.email}/token", self.api_token),
                headers=headers,
                json=data,
                timeout=30
            )
            safe_log_info(f"Zendesk API response status code: {sanitize_for_logging(str(response.status_code))}")
            
            response.raise_for_status()
            response_data = response.json()
            safe_log_info(f"Successfully updated Zendesk ticket {sanitize_for_logging(str(ticket_id))}")
            return response_data
        except requests.exceptions.Timeout:
            safe_log_error("Update request to Zendesk API timed out")
            return None
        except requests.exceptions.RequestException as e:
            safe_log_error(f"Error updating Zendesk ticket: {sanitize_for_logging(str(e))}")
            if hasattr(e, 'response') and e.response is not None and e.response.status_code < 500:
                safe_log_error(f"Error response body: {sanitize_for_logging(e.response.text[:1000])}")
            return None

    def update_ticket(
        self,
        ticket_id: int,
        subject: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        public: bool = False,
        status: Optional[str] = None
    ) -> Optional[dict]:
        """
        Update an existing Zendesk ticket
        
        Args:
            ticket_id: ID of the ticket to update
            subject: New subject for the ticket (optional)
            description: New description/comment to add (optional)  
            tags: New tags for the ticket (optional)
            public: Whether the comment should be public (default: False)
            status: New status for the ticket (optional)
            
        Returns:
            dict: Response from Zendesk API if successful, None if failed
        """
        # Validate ticket_id
        if not isinstance(ticket_id, int) or ticket_id <= 0:
            safe_log_error("Invalid ticket ID")
            return None
        
        url = f"{self.base_url}/tickets/{ticket_id}.json"
        
        # Validate inputs
        if not self._validate_update_inputs(subject, description, tags, status):
            return None
        
        safe_log_info(f"Updating Zendesk ticket {sanitize_for_logging(str(ticket_id))}")
        
        # Prepare the update data
        data = self._prepare_update_data(subject, description, tags, status, public)
        
        # Make the API request
        return self._make_update_request(url, data, ticket_id)

    def search_user_by_phone(self, phone_number: str) -> List[Dict[str, Any]]:
        """
        Search for users by phone number and return their details
        
        Args:
            phone_number: Phone number to search for (can include formatting)
            
        Returns:
            List of user dictionaries if found, empty list if not found or error
        """
        # Validate phone number format first
        if not re.match(r'^\+\d{10,15}$', phone_number):
            safe_log_error("Invalid phone number format for search")
            return []
        
        # Remove non-numeric characters from phone number (spaces, dashes, etc.)
        clean_phone = ''.join(filter(str.isdigit, phone_number.replace('+', '')))
        
        # Create search query for finding user by phone
        search_query = f"type:user phone:{clean_phone}"
        
        url = f"{self.base_url}/search.json"
        params = {
            "query": search_query
        }
        
        headers = {
            "User-Agent": USER_AGENT
        }
        
        safe_log_info("Searching for Zendesk user")
        safe_log_debug(f"Clean phone number for search: {sanitize_for_logging(clean_phone)}")
        
        try:
            response = self.session.get(
                url,
                auth=(f"{self.email}/token", self.api_token),
                params=params,
                headers=headers,
                timeout=30
            )
            safe_log_info(f"Zendesk API search response status code: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            users = data.get('results', [])
            
            # Limit the number of returned users for security
            users = users[:10]
            
            if users:
                safe_log_info(f"Found {len(users)} user(s)")
                for user in users:
                    safe_log_debug(f"Found user ID: {user.get('id', 'N/A')}")
            else:
                safe_log_info("No users found")
            
            return users
            
        except requests.exceptions.Timeout:
            safe_log_error("Search request to Zendesk API timed out")
            return []
        except requests.exceptions.RequestException as e:
            safe_log_error(f"Error searching Zendesk users: {sanitize_for_logging(str(e))}")
            if hasattr(e, 'response') and e.response is not None and e.response.status_code < 500:
                safe_log_error(f"Error response body: {sanitize_for_logging(e.response.text[:1000])}")
            return []

    def get_user_name_by_phone(self, phone_number: str) -> Optional[str]:
        """
        Get the name of the first user found with the given phone number
        
        Args:
            phone_number: Phone number to search for
            
        Returns:
            str: User's name if found, None if not found
        """
        users = self.search_user_by_phone(phone_number)
        if users:
            name = users[0].get('name', 'Name not available')
            safe_log_info(f"Retrieved name '{sanitize_for_logging(name)}' for phone number {sanitize_for_logging(phone_number)}")
            return name
        safe_log_info(f"No name found for phone number {sanitize_for_logging(phone_number)}")
        return None

    def search_users_by_name_pattern(self, name_pattern: str) -> List[Dict[str, Any]]:
        """
        Search for users whose names start with the given pattern
        
        Args:
            name_pattern: The pattern to search for in user names
            
        Returns:
            List of user dictionaries if found, empty list if not found or error
        """
        url = f"{self.base_url}/search.json"
        params = {
            "query": f"type:user name:\"{name_pattern}*\""
        }
        
        safe_log_info(f"Searching for Zendesk users with name pattern: {sanitize_for_logging(name_pattern)}")
        
        try:
            response = requests.get(
                url,
                auth=(f"{self.email}/token", self.api_token),
                params=params
            )
            safe_log_info(f"Zendesk API search response status code: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            users = data.get('results', [])
            
            if users:
                safe_log_info(f"Found {len(users)} user(s) matching pattern '{sanitize_for_logging(name_pattern)}'")
                for user in users:
                    safe_log_debug(f"Found user: {sanitize_for_logging(user.get('name', 'N/A'))} (ID: {sanitize_for_logging(str(user.get('id', 'N/A')))})")
            else:
                safe_log_info(f"No users found with name pattern '{sanitize_for_logging(name_pattern)}'")
            
            return users
            
        except requests.exceptions.RequestException as e:
            safe_log_error(f"Error searching Zendesk users: {sanitize_for_logging(str(e))}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                safe_log_error(f"Error response body: {sanitize_for_logging(e.response.text)}")
            return []

    def delete_user(self, user_id: int) -> bool:
        """
        Delete a user from Zendesk
        
        Args:
            user_id: The ID of the user to delete
            
        Returns:
            bool: True if successful, False if failed
        """
        url = f"{self.base_url}/users/{user_id}.json"
        
        safe_log_info(f"Attempting to delete Zendesk user with ID: {user_id}")
        
        try:
            response = requests.delete(
                url,
                auth=(f"{self.email}/token", self.api_token)
            )
            safe_log_info(f"Zendesk API delete response status code: {response.status_code}")
            
            response.raise_for_status()
            safe_log_info(f"Successfully deleted user {user_id}")
            return True
            
        except requests.exceptions.RequestException as e:
            safe_log_error(f"Error deleting Zendesk user: {sanitize_for_logging(str(e))}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                safe_log_error(f"Error response body: {sanitize_for_logging(e.response.text)}")
            return False

    def get_user_tickets(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all tickets for a specific user
        
        Args:
            user_id: The ID of the user
            
        Returns:
            List of ticket dictionaries if found, empty list if not found or error
        """
        url = f"{self.base_url}/users/{user_id}/tickets/requested.json"
        
        safe_log_info(f"Getting tickets for user ID: {user_id}")
        
        try:
            response = requests.get(
                url,
                auth=(f"{self.email}/token", self.api_token)
            )
            safe_log_info(f"Zendesk API response status code: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            tickets = data.get('tickets', [])
            
            if tickets:
                safe_log_info(f"Found {len(tickets)} ticket(s) for user {user_id}")
                for ticket in tickets:
                    safe_log_debug(f"Found ticket: {ticket.get('id')} (Status: {ticket.get('status')})")
            else:
                safe_log_info(f"No tickets found for user {user_id}")
            
            return tickets
            
        except requests.exceptions.RequestException as e:
            safe_log_error(f"Error getting user tickets: {sanitize_for_logging(str(e))}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                safe_log_error(f"Error response body: {sanitize_for_logging(e.response.text)}")
            return []

    def close_ticket(self, ticket_id: int) -> bool:
        """
        Close a specific ticket
        
        Args:
            ticket_id: The ID of the ticket to close
            
        Returns:
            bool: True if successful, False if failed
        """
        return self.update_ticket(
            ticket_id=ticket_id,
            status="closed",
            description="Ticket closed automatically as part of user cleanup.",
            public=False
        ) is not None

    def safe_delete_user(self, user_id: int, user_name: str) -> bool:
        """
        Safely delete a user by first closing all their tickets
        
        Args:
            user_id: The ID of the user to delete
            user_name: The name of the user (for logging purposes)
            
        Returns:
            bool: True if successful, False if failed
        """
        # First get all tickets for the user
        tickets = self.get_user_tickets(user_id)
        
        # Close all open tickets
        for ticket in tickets:
            if ticket.get('status') != 'closed':
                ticket_id = ticket.get('id')
                safe_log_info(f"Closing ticket {ticket_id} for user {user_name} (ID: {user_id})")
                if not self.close_ticket(ticket_id):
                    safe_log_error(f"Failed to close ticket {sanitize_for_logging(str(ticket_id))}")
                    return False
                # Add a small delay between ticket closures
                time.sleep(1)
        
        # Now try to delete the user
        safe_log_info(f"All tickets closed, attempting to delete user {user_name} (ID: {user_id})")
        return self.delete_user(user_id) 