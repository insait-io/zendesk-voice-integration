import os
import requests
import logging
import time
import re
from typing import List, Optional, Dict, Any
from urllib.parse import quote

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Disable debug logging in production
if os.getenv('FLASK_ENV') != 'development':
    logging.getLogger().setLevel(logging.WARNING)

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
        
        logging.info(f"Initialized ZendeskAPI with domain: {self._sanitize_domain(self.domain)}")

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
                    raise ValueError(f"Potentially malicious content detected")
        
        return True

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
        try:
            self._validate_input(subject)
            self._validate_input(description)
            for tag in tags:
                self._validate_input(tag)
        except ValueError as e:
            logging.error(f"Input validation failed: {e}")
            return None
        
        # Validate phone number format
        if not re.match(r'^\+\d{10,15}$', requester_phone):
            logging.error("Invalid phone number format")
            return None
        
        logging.info(f"Creating Zendesk ticket")
        logging.debug(f"Ticket subject: {subject}")
        logging.debug(f"Ticket tags: {tags}")
        
        # Look up user by phone number first
        users = self.search_user_by_phone(requester_phone)
        
        # Find the most appropriate user (prefer users with actual names over 'Customer')
        selected_user = None
        if users:
            # First try to find a user with a name other than 'Customer'
            named_users = [u for u in users if u.get('name') and u.get('name').lower() != 'customer']
            if named_users:
                selected_user = named_users[0]
                logging.info(f"Selected named user (ID: {selected_user.get('id')})")
            else:
                # If no named users found, use the first user
                selected_user = users[0]
                logging.info(f"Selected first available user (ID: {selected_user.get('id')})")

        # Prepare the ticket data
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
            logging.info(f"Creating ticket for existing user ID: {selected_user.get('id')}")
        else:
            # Only create a new user if we didn't find any existing ones
            logging.info("No existing user found, creating ticket with new user")
            data["ticket"]["requester"] = {
                "phone": requester_phone,
                "name": "New Caller - Insait AI Agent"  # Default name for new users
            }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Insait-Voice-Integration/2.0"
        }
        
        sanitized_data = self._sanitize_for_logging(data)
        logging.debug(f"Request payload: {sanitized_data}")
        
        try:
            logging.info(f"Sending request to Zendesk API: {url}")
            response = self.session.post(
                url,
                auth=(f"{self.email}/token", self.api_token),
                headers=headers,
                json=data,
                timeout=30
            )
            logging.info(f"Zendesk API response status code: {response.status_code}")
            
            response.raise_for_status()
            response_data = response.json()
            logging.info(f"Successfully created Zendesk ticket with ID: {response_data.get('ticket', {}).get('id')}")
            return response_data
        except requests.exceptions.Timeout:
            logging.error("Request to Zendesk API timed out")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Error creating Zendesk ticket: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logging.error(f"Error response status: {e.response.status_code}")
                if e.response.status_code < 500:  # Don't log server errors content
                    logging.error(f"Error response body: {e.response.text[:1000]}")
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
            subject: New ticket subject (optional)
            description: New comment to add to the ticket (optional)
            tags: New list of tags (optional, will replace existing tags)
            public: Whether the comment should be public (default: False)
            status: New ticket status (optional) - can be 'open', 'pending', 'solved', 'closed'
            
        Returns:
            dict: Response from Zendesk API if successful, None if failed
        """
        # Validate ticket_id
        if not isinstance(ticket_id, int) or ticket_id <= 0:
            logging.error("Invalid ticket ID")
            return None
        
        url = f"{self.base_url}/tickets/{ticket_id}.json"
        logging.info(f"Updating Zendesk ticket: {ticket_id}")
        
        # Initialize the ticket data
        data = {"ticket": {}}
        
        # Validate and add fields only if they are provided
        if subject is not None:
            try:
                self._validate_input(subject)
                data["ticket"]["subject"] = subject[:255]  # Limit subject length
                logging.debug(f"Updating ticket subject")
            except ValueError as e:
                logging.error(f"Subject validation failed: {e}")
                return None
            
        if description is not None:
            try:
                self._validate_input(description)
                # For updates, comments must be added to a separate comment field
                data["ticket"]["comment"] = {
                    "body": description[:65535],  # Limit description length
                    "public": public
                }
                logging.debug(f"Adding new comment to ticket")
            except ValueError as e:
                logging.error(f"Description validation failed: {e}")
                return None
            
        if tags is not None:
            for tag in tags:
                try:
                    self._validate_input(tag)
                except ValueError as e:
                    logging.error(f"Tag validation failed: {e}")
                    return None
            data["ticket"]["tags"] = tags[:10]  # Limit number of tags
            logging.debug(f"Updating ticket tags")
            
        if status is not None:
            valid_statuses = ['open', 'pending', 'solved', 'closed']
            if status.lower() not in valid_statuses:
                logging.error(f"Invalid status '{status}'. Must be one of: {valid_statuses}")
                return None
            data["ticket"]["status"] = status.lower()
            logging.debug(f"Updating ticket status: {status}")
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Insait-Voice-Integration/2.0"
        }
        
        sanitized_data = self._sanitize_for_logging(data)
        logging.debug(f"Request payload: {sanitized_data}")
        
        try:
            logging.info(f"Sending PUT request to Zendesk API: {url}")
            response = self.session.put(
                url,
                auth=(f"{self.email}/token", self.api_token),
                headers=headers,
                json=data,
                timeout=30
            )
            logging.info(f"Zendesk API response status code: {response.status_code}")
            
            response.raise_for_status()
            response_data = response.json()
            logging.info(f"Successfully updated Zendesk ticket {ticket_id}")
            return response_data
        except requests.exceptions.Timeout:
            logging.error("Update request to Zendesk API timed out")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Error updating Zendesk ticket: {str(e)}")
            if hasattr(e, 'response') and e.response is not None and e.response.status_code < 500:
                logging.error(f"Error response body: {e.response.text[:1000]}")
            return None

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
            logging.error("Invalid phone number format for search")
            return []
        
        # Remove non-numeric characters from phone number (spaces, dashes, etc.)
        clean_phone = ''.join(filter(str.isdigit, phone_number.replace('+', '')))
        
        # URL encode the search query to prevent injection
        search_query = f"type:user phone:{clean_phone}"
        encoded_query = quote(search_query)
        
        url = f"{self.base_url}/search.json"
        params = {
            "query": search_query
        }
        
        headers = {
            "User-Agent": "Insait-Voice-Integration/2.0"
        }
        
        logging.info(f"Searching for Zendesk user")
        logging.debug(f"Clean phone number for search: {clean_phone}")
        
        try:
            response = self.session.get(
                url,
                auth=(f"{self.email}/token", self.api_token),
                params=params,
                headers=headers,
                timeout=30
            )
            logging.info(f"Zendesk API search response status code: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            users = data.get('results', [])
            
            # Limit the number of returned users for security
            users = users[:10]
            
            if users:
                logging.info(f"Found {len(users)} user(s)")
                for user in users:
                    logging.debug(f"Found user ID: {user.get('id', 'N/A')}")
            else:
                logging.info(f"No users found")
            
            return users
            
        except requests.exceptions.Timeout:
            logging.error("Search request to Zendesk API timed out")
            return []
        except requests.exceptions.RequestException as e:
            logging.error(f"Error searching Zendesk users: {str(e)}")
            if hasattr(e, 'response') and e.response is not None and e.response.status_code < 500:
                logging.error(f"Error response body: {e.response.text[:1000]}")
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
            logging.info(f"Retrieved name '{name}' for phone number {phone_number}")
            return name
        logging.info(f"No name found for phone number {phone_number}")
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
        
        logging.info(f"Searching for Zendesk users with name pattern: {name_pattern}")
        
        try:
            response = requests.get(
                url,
                auth=(f"{self.email}/token", self.api_token),
                params=params
            )
            logging.info(f"Zendesk API search response status code: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            users = data.get('results', [])
            
            if users:
                logging.info(f"Found {len(users)} user(s) matching pattern '{name_pattern}'")
                for user in users:
                    logging.debug(f"Found user: {user.get('name', 'N/A')} (ID: {user.get('id', 'N/A')})")
            else:
                logging.info(f"No users found with name pattern '{name_pattern}'")
            
            return users
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Error searching Zendesk users: {str(e)}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logging.error(f"Error response body: {e.response.text}")
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
        
        logging.info(f"Attempting to delete Zendesk user with ID: {user_id}")
        
        try:
            response = requests.delete(
                url,
                auth=(f"{self.email}/token", self.api_token)
            )
            logging.info(f"Zendesk API delete response status code: {response.status_code}")
            
            response.raise_for_status()
            logging.info(f"Successfully deleted user {user_id}")
            return True
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Error deleting Zendesk user: {str(e)}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logging.error(f"Error response body: {e.response.text}")
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
        
        logging.info(f"Getting tickets for user ID: {user_id}")
        
        try:
            response = requests.get(
                url,
                auth=(f"{self.email}/token", self.api_token)
            )
            logging.info(f"Zendesk API response status code: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            tickets = data.get('tickets', [])
            
            if tickets:
                logging.info(f"Found {len(tickets)} ticket(s) for user {user_id}")
                for ticket in tickets:
                    logging.debug(f"Found ticket: {ticket.get('id')} (Status: {ticket.get('status')})")
            else:
                logging.info(f"No tickets found for user {user_id}")
            
            return tickets
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Error getting user tickets: {str(e)}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logging.error(f"Error response body: {e.response.text}")
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
                logging.info(f"Closing ticket {ticket_id} for user {user_name} (ID: {user_id})")
                if not self.close_ticket(ticket_id):
                    logging.error(f"Failed to close ticket {ticket_id}")
                    return False
                # Add a small delay between ticket closures
                time.sleep(1)
        
        # Now try to delete the user
        logging.info(f"All tickets closed, attempting to delete user {user_name} (ID: {user_id})")
        return self.delete_user(user_id) 