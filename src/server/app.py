import os
import logging
import time
import re
import sys
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from datetime import datetime, timezone
from google.cloud import firestore
from google.api_core.exceptions import GoogleAPIError
import json

# Add the src directory to the Python path for relative imports  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.zendesk.api import ZendeskAPI
from src.utils.logging_utils import sanitize_for_logging, safe_log_info, safe_log_warning, safe_log_error, safe_log_debug

load_dotenv()

# Configure secure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Disable debug logging in production
if os.getenv('FLASK_ENV') != 'development':
    logging.getLogger().setLevel(logging.WARNING)

def sanitize_phone_number(phone_number):
    """
    Sanitize phone number for logging and processing.
    
    Args:
        phone_number (str): The phone number to sanitize
        
    Returns:
        str: Sanitized phone number (partial masking for logs)
    """
    if not phone_number or len(phone_number) < 4:
        return "****"
    return phone_number[:3] + "*" * (len(phone_number) - 6) + phone_number[-3:]

def validate_phone_number(phone_number):
    """
    Validate phone number format.
    
    Args:
        phone_number (str): The phone number to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not phone_number:
        return False
    
    # Remove all non-numeric characters except +
    cleaned = re.sub(r'[^\d+]', '', phone_number)
    
    # Basic validation: should start with + and have 10-15 digits
    pattern = r'^\+\d{10,15}$'
    return bool(re.match(pattern, cleaned))

def validate_call_data(data):
    """
    Validate incoming call data.
    
    Args:
        data (dict): The call data to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Invalid data format"
    
    required_fields = ['event', 'call']
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    call_data = data.get('call', {})
    if not isinstance(call_data, dict):
        return False, "Invalid call data format"
    
    call_required_fields = ['call_id', 'from_number']
    for field in call_required_fields:
        if field not in call_data:
            return False, f"Missing required call field: {field}"
    
    # Validate phone number
    if not validate_phone_number(call_data.get('from_number')):
        return False, "Invalid phone number format"
    
    # Validate event type
    valid_events = ['call_started', 'call_ended']
    if data.get('event') not in valid_events:
        return False, f"Invalid event type. Must be one of: {valid_events}"
    
    return True, None

def is_phone_number_allowed(phone_number):
    """
    Check if a phone number is allowed to make API requests.
    
    Args:
        phone_number (str): The phone number to check
        
    Returns:
        bool: True if the phone number is allowed, False otherwise
        
    Environment Variable:
        ALLOWED_PHONE_NUMBERS: Comma-separated list of allowed phone numbers.
                              If not set, all phone numbers are allowed.
    """
    allowed_numbers = os.getenv('ALLOWED_PHONE_NUMBERS')
    
    if not allowed_numbers:
        return True
    
    allowed_list = [num.strip() for num in allowed_numbers.split(',')]
    
    return phone_number in allowed_list

# Initialize Firestore client
firestore_client = None
try:
    # Initialize Firestore client
    firestore_client = firestore.Client()
    safe_log_info("Firestore initialized successfully")
except Exception as e:
    safe_log_warning(f"Firestore initialization failed: {sanitize_for_logging(str(e))}. Continuing without Firestore.")
    firestore_client = None

app = Flask(__name__)

# Configure rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per hour", "20 per minute"],
    storage_uri="memory://"
)

# Security headers middleware
@app.after_request
def after_request(response):
    """Add security headers to all responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response

def store_processed_call(event_call_key, event, call_id):
    """Store processed call information in Firestore."""
    if not firestore_client:
        return False
    
    try:
        doc_ref = firestore_client.collection('processed_calls').document(event_call_key)
        doc_ref.set({
            'timestamp': datetime.now(),
            'event': event,
            'call_id': call_id
        })
        return True
    except GoogleAPIError as e:
        safe_log_error(f"Error storing processed call: {sanitize_for_logging(str(e))}")
        return False

def check_processed_call(event_call_key):
    """Check if call event has already been processed."""
    if not firestore_client:
        return False
    
    try:
        doc_ref = firestore_client.collection('processed_calls').document(event_call_key)
        doc = doc_ref.get()
        return doc.exists
    except GoogleAPIError as e:
        safe_log_error(f"Error checking processed call: {sanitize_for_logging(str(e))}")
        return False

def store_active_ticket(phone_number, ticket_id):
    """Store active ticket information in Firestore."""
    if not firestore_client:
        return False
    
    try:
        doc_ref = firestore_client.collection('active_tickets').document(phone_number)
        doc_ref.set({
            'ticket_id': ticket_id,
            'timestamp': datetime.now()
        })
        return True
    except GoogleAPIError as e:
        safe_log_error(f"Error storing active ticket: {sanitize_for_logging(str(e))}")
        return False

def get_active_ticket(phone_number):
    """Get active ticket for a phone number."""
    if not firestore_client:
        return None
    
    try:
        doc_ref = firestore_client.collection('active_tickets').document(phone_number)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            return data.get('ticket_id')
        return None
    except GoogleAPIError as e:
        safe_log_error(f"Error getting active ticket: {sanitize_for_logging(str(e))}")
        return None

def remove_active_ticket(phone_number):
    """Remove active ticket from Firestore."""
    if not firestore_client:
        return False
    
    try:
        doc_ref = firestore_client.collection('active_tickets').document(phone_number)
        doc_ref.delete()
        return True
    except GoogleAPIError as e:
        safe_log_error(f"Error removing active ticket: {sanitize_for_logging(str(e))}")
        return False

def get_all_active_tickets():
    """Get all active tickets for debugging purposes."""
    if not firestore_client:
        return {}
    
    try:
        docs = firestore_client.collection('active_tickets').stream()
        active_tickets = {}
        for doc in docs:
            data = doc.to_dict()
            active_tickets[doc.id] = data.get('ticket_id')
        return active_tickets
    except GoogleAPIError as e:
        safe_log_error(f"Error getting all active tickets: {sanitize_for_logging(str(e))}")
        return {}



def _validate_request():
    """Validate incoming request size and content type."""
    # Validate request size (max 1MB)
    if request.content_length and request.content_length > 1024 * 1024:
        safe_log_warning("Request too large")
        return jsonify({"error": "Request too large"}), 413
    
    # Validate content type
    if not request.is_json:
        safe_log_warning("Invalid content type")
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    return None

def _validate_and_extract_call_data():
    """Validate and extract call data from request."""
    data = request.json
    
    # Validate input data
    is_valid, error_message = validate_call_data(data)
    if not is_valid:
        safe_log_warning(f"Invalid call data: {sanitize_for_logging(error_message)}")
        return None, jsonify({"error": error_message}), 400
    
    call_id = data.get('call', {}).get('call_id')
    event = data.get('event')
    phone = data['call']['from_number']
    
    return (call_id, event, phone, data), None, None

def _check_authorization_and_duplicates(phone, event, call_id):
    """Check phone number authorization and duplicate processing."""
    sanitized_phone = sanitize_phone_number(phone)
    
    if not is_phone_number_allowed(phone):
        safe_log_warning(f"Phone number {sanitized_phone} is not in the allowed list")
        return None, jsonify({
            "error": "Phone number not authorized", 
            "message": "This phone number is not authorized to create tickets"
        }), 403
    
    event_call_key = f"{event}_{call_id}"
    
    # Check for duplicate processing using Firestore
    if check_processed_call(event_call_key):
        safe_log_info(f"Duplicate event-call pair detected: {sanitize_for_logging(event_call_key)}, ignoring request.")
        return None, jsonify({"message": "Duplicate event-call pair, ignored"}), 200
    
    # Store processed call
    store_processed_call(event_call_key, event, call_id)
    
    return sanitized_phone, None, None

def _handle_call_started(zendesk, data, phone, call_id):
    """Handle call_started event."""
    sanitized_phone = sanitize_phone_number(phone)
    start_time = datetime.fromtimestamp(data['call']['start_timestamp'] / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    
    initial_description = f"""
Ongoing Call Information:
- Phone: {phone}
- Call Start Time: {start_time}
- Call Status: In Progress
- Call ID: {call_id}

Note: This ticket will be updated with full call details when the call ends.
"""
    
    result = zendesk.create_ticket(
        subject=f"Ongoing Call with {sanitized_phone}",
        description=initial_description,
        requester_phone=phone,
        tags=["call", "insait-ai-agent", "in-progress"]
    )
    
    if result and 'ticket' in result:
        # Store active ticket in Firestore
        store_active_ticket(phone, result['ticket']['id'])
        safe_log_info(f"Created initial ticket {sanitize_for_logging(str(result['ticket']['id']))} for {sanitized_phone}")
        
        # Get current active tickets for logging (without sensitive data)
        current_active = get_all_active_tickets()
        safe_log_info(f"Current active_tickets count in Firestore: {sanitize_for_logging(str(len(current_active)))}")
        
        return jsonify({
            "message": "Initial ticket created successfully", 
            "ticket": result
        }), 201
    else:
        safe_log_error("Failed to create initial Zendesk ticket")
        return jsonify({"error": "Failed to create initial ticket"}), 500

def _handle_call_ended(zendesk, data, phone):
    """Handle call_ended event."""
    sanitized_phone = sanitize_phone_number(phone)
    
    # Get current active tickets count for logging
    current_active = get_all_active_tickets()
    safe_log_info(f"Current active_tickets count at call_ended: {sanitize_for_logging(str(len(current_active)))}")
    
    # Retry logic for finding ticket
    ticket_id = _retry_get_active_ticket(phone, sanitized_phone)
    
    if not ticket_id:
        return _create_new_ticket_for_ended_call(zendesk, data, phone, sanitized_phone)
    else:
        return _update_existing_ticket(zendesk, data, phone, sanitized_phone, ticket_id)

def _retry_get_active_ticket(phone, sanitized_phone):
    """Retry getting active ticket with exponential backoff."""
    ticket_id = get_active_ticket(phone)
    retry_count = 0
    max_retries = 5
    
    while not ticket_id and retry_count < max_retries:
        safe_log_info(f"Attempt {retry_count + 1}/{max_retries}: No active ticket found for phone number {sanitized_phone}")
        time.sleep(10)
        ticket_id = get_active_ticket(phone)
        retry_count += 1
    
    return ticket_id

def _create_new_ticket_for_ended_call(zendesk, data, phone, sanitized_phone):
    """Create a new ticket for ended call when no active ticket is found."""
    safe_log_info(f"No active ticket found for {sanitized_phone} after 5 attempts, creating new ticket")
    start_time = datetime.fromtimestamp(data['call']['start_timestamp'] / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    end_time = datetime.fromtimestamp(data['call']['end_timestamp'] / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    
    description = f"""
Completed Call Information:
- Phone: {phone}
- Call Start Time: {start_time}
- Call End Time: {end_time}
- Recording URL: {data['call'].get('recording_url', 'Not available')}
- Transcript: {data['call'].get('transcript', 'Not available')}
"""
    return zendesk.create_ticket(
        subject=f"Completed Call with {sanitized_phone}",
        description=description,
        requester_phone=phone,
        tags=["call", "insait-ai-agent", "completed"]
    )

def _update_existing_ticket(zendesk, data, phone, sanitized_phone, ticket_id):
    """Update existing ticket with call completion details."""
    safe_log_info(f"Found existing ticket {sanitize_for_logging(str(ticket_id))} for phone number {sanitized_phone}, proceeding with update")
    end_time = datetime.fromtimestamp(data['call']['end_timestamp'] / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    
    update_description = f"""
Call Completed - Updated Information:
- Call End Time: {end_time}
- Call Duration: {data['call']['duration_ms'] / 1000} seconds
- Recording URL: {data['call'].get('recording_url', 'Not available')}
- Transcript: {data['call'].get('transcript', 'Not available')}
"""
    
    result = zendesk.update_ticket(
        ticket_id=ticket_id,
        subject=f"Completed Call with {sanitized_phone}",
        description=update_description,
        tags=["call", "insait-ai-agent", "completed"],
        status="open"
    )
    
    # Remove active ticket from Firestore
    remove_active_ticket(phone)
    current_active = get_all_active_tickets()
    safe_log_info(f"Removed ticket for {sanitized_phone}. Current active_tickets count: {sanitize_for_logging(str(len(current_active)))}")
    
    return result

@app.route("/create_zendesk_ticket", methods=["POST"])
@limiter.limit("10 per minute")
def create_zendesk_ticket():
    """
    Create or update a Zendesk ticket based on call events:
    - For call_started: Create a new ticket with initial information
    - For call_ended: Update the existing ticket with call details and transcript
    
    Phone Number Filtering:
    - If ALLOWED_PHONE_NUMBERS environment variable is set, only phone numbers
      in that comma-separated list will be processed
    - If ALLOWED_PHONE_NUMBERS is not set, all phone numbers are allowed
    """
    try:
        # Validate request
        validation_error = _validate_request()
        if validation_error:
            return validation_error
        
        safe_log_info("Received request to create/update Zendesk ticket")
        
        # Extract and validate call data
        result = _validate_and_extract_call_data()
        if result[1]:  # Error response exists
            return result[1], result[2]
        
        call_id, event, phone, data = result[0]
        
        # Sanitize phone number for logging
        sanitized_phone = sanitize_phone_number(phone)
        safe_log_info(f"Processing {sanitize_for_logging(event)} for caller: {sanitized_phone}")

        # Check authorization and duplicates
        auth_result = _check_authorization_and_duplicates(phone, event, call_id)
        if auth_result[1]:  # Error response exists
            return auth_result[1], auth_result[2]
        
        if event not in ['call_started', 'call_ended']:
            safe_log_info(f"Ignoring event: {sanitize_for_logging(event)}")
            return jsonify({"error": "Not processing events other than call_started or call_ended"}), 200

        zendesk = ZendeskAPI()

        if event == 'call_started':
            return _handle_call_started(zendesk, data, phone, call_id)
        elif event == 'call_ended':
            result = _handle_call_ended(zendesk, data, phone)
            
            if result:
                safe_log_info("Successfully updated/created ticket for completed call")
                return jsonify({
                    "message": "Ticket updated/created successfully", 
                    "ticket": result
                }), 200
            else:
                safe_log_error("Failed to update/create Zendesk ticket for completed call")
                return jsonify({"error": "Failed to update/create ticket"}), 500
                
    except Exception as e:
        safe_log_error(f"Error processing Zendesk ticket: {sanitize_for_logging(str(e))}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route("/test_zendesk_flow", methods=["GET"])
@limiter.limit("5 per minute")
def test_zendesk_flow():
    """
    Test endpoint to verify Zendesk integration is working.
    """
    try:
        zendesk = ZendeskAPI()
        
        test_phone = "+15551234567"
        
        # Validate test phone number
        if not validate_phone_number(test_phone):
            return jsonify({
                "success": False,
                "error": "Invalid test phone number"
            }), 400
        
        users = zendesk.search_user_by_phone(test_phone)
        
        test_result = zendesk.create_ticket(
            subject="Test Ticket - Voice Integration",
            description="This is a test ticket created by the voice integration system.",
            requester_phone=test_phone,
            tags=["test", "voice-integration"],
            public=False
        )
        
        if test_result and 'ticket' in test_result:
            ticket_id = test_result['ticket']['id']
            
            update_result = zendesk.update_ticket(
                ticket_id=ticket_id,
                description="Test ticket updated successfully.",
                tags=["test", "voice-integration", "updated"],
                status="solved"
            )
            
            return jsonify({
                "success": True,
                "test_results": {
                    "user_search": len(users),
                    "ticket_created": True,
                    "ticket_id": ticket_id,
                    "ticket_updated": update_result is not None
                },
                "message": "Zendesk integration test completed successfully"
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": "Failed to create test ticket"
            }), 500
            
    except Exception as e:
        safe_log_error(f"Error in Zendesk flow test: {sanitize_for_logging(str(e))}")
        return jsonify({"error": "Test failed"}), 500

@app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint.
    """
    try:
        # Check Firestore connection
        firestore_status = "connected" if firestore_client else "disconnected"
        
        return jsonify({
            "status": "healthy",
            "service": "zendesk-voice-server",
            "timestamp": datetime.now().isoformat(),
            "firestore": firestore_status,
            "version": "2.0.1"
        }), 200
    except Exception as e:
        safe_log_error(f"Health check failed: {sanitize_for_logging(str(e))}")
        return jsonify({
            "status": "unhealthy",
            "service": "zendesk-voice-server",
            "timestamp": datetime.now().isoformat(),
            "error": "Health check failed"
        }), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle request entity too large error."""
    return jsonify({"error": "Request entity too large"}), 413

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded error."""
    return jsonify({"error": "Rate limit exceeded", "message": str(e)}), 429

@app.errorhandler(404)
def not_found(error):
    """Handle not found error."""
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Handle method not allowed error."""
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def internal_error(error):
    """Handle internal server error."""
    safe_log_error(f"Internal server error: {sanitize_for_logging(str(error))}")
    return jsonify({"error": "Internal server error"}), 500

# Production web applications should not include debug entry points
# Use a proper WSGI server like Gunicorn instead