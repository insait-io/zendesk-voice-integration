#!/usr/bin/env python3
"""
Entry point for the Zendesk Voice Server application.
This file is used by gunicorn to start the Flask application.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from server.app import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)