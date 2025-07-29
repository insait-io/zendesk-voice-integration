import os
import logging
import time
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db

from zendesk.api import ZendeskAPI

load_dotenv()

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

active_tickets = {}

processed_calls_ref = None
active_tickets_ref = None

try:
    cred = credentials.Certificate('firebase-credentials.json')
    firebase_admin.initialize_app(cred, {
        'databaseURL': os.getenv('FIREBASE_DATABASE_URL', '')
    })
    processed_calls_ref = db.reference('processed_calls')
    active_tickets_ref = db.reference('active_tickets')
    logging.info("Firebase initialized successfully")
except Exception as e:
    logging.warning(f"Firebase initialization failed: {e}. Continuing without Firebase.")
    processed_calls_ref = None
    active_tickets_ref = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)



@app.route("/create_zendesk_ticket", methods=["POST"])
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
        logging.info("Received request to create/update Zendesk ticket")
        data = request.json
        logging.info(f"{data['event']}")

        call_id = data.get('call', {}).get('call_id')
        event = data.get('event')
        phone = data['call']['from_number']

        if not call_id or not event:
            logging.warning("Missing call_id or event in request")
            return jsonify({"error": "Missing call_id or event"}), 400
        
        if not is_phone_number_allowed(phone):
            logging.warning(f"Phone number {phone} is not in the allowed list")
            return jsonify({
                "error": "Phone number not authorized", 
                "message": "This phone number is not authorized to create tickets"
            }), 403
        
        event_call_key = f"{event}_{call_id}"
        
        if processed_calls_ref and processed_calls_ref.child(event_call_key).get():
            logging.info(f"Duplicate event-call pair detected: {event_call_key}, ignoring request.")
            return jsonify({"message": "Duplicate event-call pair, ignored"}), 200
        
        if processed_calls_ref:
            processed_calls_ref.child(event_call_key).set({
                'timestamp': datetime.now().isoformat(),
                'event': event,
                'call_id': call_id
            })

        if event not in ['call_started', 'call_ended']:
            logging.info(f"Ignoring event: {event}")
            return jsonify({"error": "Not processing events other than call_started or call_ended"}), 200

        logging.info(f"Processing {event} for caller: {phone}")
        zendesk = ZendeskAPI()

        if event == 'call_started':
            start_time = datetime.utcfromtimestamp(data['call']['start_timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
            
            initial_description = f"""
Ongoing Call Information:
- Phone: {phone}
- Call Start Time: {start_time}
- Call Status: In Progress
- Call ID: {call_id}

Note: This ticket will be updated with full call details when the call ends.
"""
            
            result = zendesk.create_ticket(
                subject=f"Ongoing Call with {phone}",
                description=initial_description,
                requester_phone=phone,
                tags=["call", "insait-ai-agent", "in-progress"]
            )
            
            if result and 'ticket' in result:
                if active_tickets_ref:
                    active_tickets_ref.child(phone).set(result['ticket']['id'])
                logging.info(f"Created initial ticket {result['ticket']['id']} for {phone}")
                current_active = active_tickets_ref.get() or {}
                logging.info(f"Current active_tickets state in Firebase: {current_active}")
                return jsonify({
                    "message": "Initial ticket created successfully", 
                    "ticket": result
                }), 201
            else:
                logging.error("Failed to create initial Zendesk ticket")
                return jsonify({"error": "Failed to create initial ticket"}), 500

        elif event == 'call_ended':
            ticket_id = active_tickets_ref.child(phone).get()
            current_active = active_tickets_ref.get() or {}
            logging.info(f"Current active_tickets state at call_ended: {current_active}")
            retry_count = 0
            max_retries = 5
            
            while not ticket_id and retry_count < max_retries:
                logging.info(f"Attempt {retry_count + 1}/{max_retries}: No active ticket found for phone number {phone} in active_tickets dictionary")
                time.sleep(10)
                ticket_id = active_tickets_ref.child(phone).get()
                retry_count += 1
                
            if not ticket_id:
                logging.info(f"No active ticket found for {phone} after {max_retries} attempts, creating new ticket")
                start_time = datetime.utcfromtimestamp(data['call']['start_timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                end_time = datetime.utcfromtimestamp(data['call']['end_timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                
                description = f"""
Completed Call Information:
- Phone: {phone}
- Call Start Time: {start_time}
- Call End Time: {end_time}
- Recording URL: {data['call'].get('recording_url', 'Not available')}
- Transcript: {data['call'].get('transcript', 'Not available')}
"""
                result = zendesk.create_ticket(
                    subject=f"Completed Call with {phone}",
                    description=description,
                    requester_phone=phone,
                    tags=["call", "insait-ai-agent", "completed"]
                )
            else:
                logging.info(f"Found existing ticket {ticket_id} for phone number {phone}, proceeding with update")
                end_time = datetime.utcfromtimestamp(data['call']['end_timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                
                update_description = f"""
Call Completed - Updated Information:
- Call End Time: {end_time}
- Call Duration: {data['call']['duration_ms'] / 1000} seconds
- Recording URL: {data['call'].get('recording_url', 'Not available')}
- Transcript: {data['call'].get('transcript', 'Not available')}
"""
                
                result = zendesk.update_ticket(
                    ticket_id=ticket_id,
                    subject=f"Completed Call with {phone}",
                    description=update_description,
                    tags=["call", "insait-ai-agent", "completed"],
                    status="open"
                )
                
                if active_tickets_ref:
                    active_tickets_ref.child(phone).delete()
                    current_active = active_tickets_ref.get() or {}
                    logging.info(f"Removed ticket for {phone}. Current active_tickets state: {current_active}")
            
            if result:
                logging.info(f"Successfully updated/created ticket for completed call")
                return jsonify({
                    "message": "Ticket updated/created successfully", 
                    "ticket": result
                }), 200
            else:
                logging.error("Failed to update/create Zendesk ticket for completed call")
                return jsonify({"error": "Failed to update/create ticket"}), 500
                
    except Exception as e:
        logging.error(f"Error processing Zendesk ticket: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/test_zendesk_flow", methods=["GET"])
def test_zendesk_flow():
    """
    Test endpoint to verify Zendesk integration is working.
    """
    try:
        zendesk = ZendeskAPI()
        
        test_phone = "+15551234567"
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
        logging.error(f"Error in Zendesk flow test: {str(e)}")
        return jsonify({"error": f"Test failed: {str(e)}"}), 500

@app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint.
    """
    return jsonify({
        "status": "healthy",
        "service": "zendesk-voice-server",
        "timestamp": datetime.now().isoformat()
    }), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)