#!/usr/bin/env python3
"""
Entry point for the Zendesk Voice Server application.
This file is used by gunicorn to start the Flask application.
"""

import os
import sys
import logging

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from server.app import app

# Disable debug mode in production
if os.getenv('FLASK_ENV') == 'production':
    app.config['DEBUG'] = False
    app.config['TESTING'] = False

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    
    # Security: never run debug mode in production
    if os.getenv('FLASK_ENV') == 'production':
        debug_mode = False
    
    app.run(host="0.0.0.0", port=port, debug=debug_mode, threaded=True)