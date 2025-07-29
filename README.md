<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://cdn.insait.io/public/logos/full-logo-light.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://cdn.insait.io/public/logos/full-logo-color.svg">
  <img alt="Insait Agent Platform" src="https://cdn.insait.io/public/logos/full-logo-light.svg" height="80">
</picture>

</br>

</br>

</div>

# Zendesk Voice Server

A Flask-based server for automatically creating Zendesk tickets from voice call events. This application integrates with voice call services to process call data and create support tickets in Zendesk.

## Features

- **Automatic Ticket Creation**: Creates Zendesk tickets from voice call events
- **Phone Number Filtering**: Optional restriction of API access to authorized phone numbers
- **User Management**: Handles existing and new users based on phone numbers
- **Call Processing**: Processes completed calls and extracts relevant information
- **Firebase Integration**: Stores processed calls and active tickets
- **Comprehensive Logging**: Detailed logging for debugging and monitoring
- **RESTful API**: Clean API endpoints for call processing and ticket management

## Project Structure

```
zendesk-voice-server/
├── src/
│   ├── zendesk/
│   │   ├── __init__.py
│   │   └── api.py              # Zendesk API client
│   ├── server/
│   │   ├── __init__.py
│   │   └── app.py              # Flask application
│   ├── utils/
│   │   ├── __init__.py
│   │   └── helpers.py          # Utility functions
│   └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── test_zendesk_api.py     # Zendesk API tests
│   ├── test_server.py          # Server endpoint tests
│   └── test_utils.py           # Utility function tests
├── config/
│   └── settings.py             # Configuration settings
├── docs/                       # Documentation
├── app.py                      # Main application entry point
├── requirements.txt             # Python dependencies
├── README.md                   # This file
└── .gitignore                  # Git ignore file
```

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd zendesk-voice-server
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Copy the example environment file and configure your settings:
   ```bash
   cp env.example .env
   ```
   
   Edit the `.env` file with your actual credentials:
   ```env
   # Zendesk Configuration
   ZENDESK_DOMAIN=your-domain.zendesk.com
   ZENDESK_EMAIL=your-email@example.com
   ZENDESK_API_TOKEN=your-api-token
   
   # Firebase Configuration
   FIREBASE_CREDENTIALS_FILE=firebase-credentials.json
   FIREBASE_DATABASE_URL=your-firebase-url
   
   # Server Configuration
   PORT=5000
   
   # Phone Number Filtering (Optional)
   # Restrict API access to specific phone numbers
   # If not set, all phone numbers are allowed
   ALLOWED_PHONE_NUMBERS=+15551234567,+15559876543
   ```

5. **Set up Firebase credentials**:
   Place your `firebase-credentials.json` file in the root directory.

## Security

⚠️ **Important Security Notes**:

- **Never commit sensitive files**: The `.gitignore` file is configured to exclude:
  - `.env` files (environment variables)
  - `firebase-credentials.json` (Firebase service account key)
  - `venv/` directory (virtual environment)
  - `__pycache__/` directories
  - Log files

- **Environment Variables**: Always use environment variables for sensitive data like API tokens, passwords, and service account keys.

- **Firebase Credentials**: Keep your Firebase service account key secure and never share it publicly.

- **Production Deployment**: In production, use proper secret management systems and ensure all sensitive data is stored securely.

## Usage

### Running the Server

**Development mode**:
```bash
python app.py
```

**Production mode**:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### API Endpoints

#### 1. Call Events Manager
**POST** `/call_events_manager`

Processes voice call events and creates Zendesk tickets.

**Request Body**:
```json
{
  "call": {
    "call_id": "call_123",
    "from_number": "+15551234567",
    "call_status": "ended",
    "start_timestamp": 1640995200000,
    "end_timestamp": 1640995260000,
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
```

**Response**:
```json
{
  "success": true,
  "ticket_id": 12345,
  "message": "Created Zendesk ticket 12345"
}
```

#### 2. Manual Ticket Creation
**POST** `/create_zendesk_ticket`

Manually create a Zendesk ticket for testing purposes.

**Request Body**:
```json
{
  "subject": "Test Ticket",
  "description": "Test description",
  "requester_phone": "+15551234567",
  "tags": ["test", "voice-call"],
  "public": false
}
```

#### 3. Zendesk Flow Test
**GET** `/test_zendesk_flow`

Test the Zendesk integration by creating and updating a test ticket.

#### 4. Health Check
**GET** `/health`

Check the server health status.

### Running Tests

```bash
# Run all tests
python -m unittest discover tests

# Run specific test file
python -m unittest tests.test_zendesk_api

# Run with coverage
pip install coverage
coverage run -m unittest discover tests
coverage report
```

## Configuration

The application uses a configuration system with different environments:

- **Development**: Debug mode, detailed logging
- **Production**: Optimized for production use
- **Testing**: Test-specific settings

Configuration is managed in `config/settings.py` and can be customized via environment variables.

## Key Components

### Zendesk API (`src/zendesk/api.py`)
- Handles all Zendesk API interactions
- Manages ticket creation, updates, and user operations
- Includes user search and management functionality

### Flask Server (`src/server/app.py`)
- Main Flask application with API endpoints
- Processes call events and manages ticket creation
- Integrates with Firebase for data persistence

### Utility Functions (`src/utils/helpers.py`)
- Phone number validation and cleaning
- Call data formatting
- Ticket subject and description generation
- Tag sanitization

## Development

### Adding New Features

1. **Create new modules** in the appropriate `src/` subdirectory
2. **Add tests** in the corresponding `tests/` file
3. **Update documentation** in the `docs/` directory
4. **Follow the existing code structure** and patterns

### Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Include docstrings for all functions and classes
- Write comprehensive tests for new functionality

## Deployment

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

### Environment Variables

Make sure to set all required environment variables in your deployment environment:

**Required:**
- `ZENDESK_DOMAIN`
- `ZENDESK_EMAIL`
- `ZENDESK_API_TOKEN`
- `FIREBASE_CREDENTIALS_FILE`

**Optional:**
- `PORT` - Server port (default: 5000)
- `ALLOWED_PHONE_NUMBERS` - Comma-separated list of authorized phone numbers. If not set, all phone numbers are allowed.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions, please contact the development team or create an issue in the repository.


