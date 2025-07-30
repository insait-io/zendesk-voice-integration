<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://cdn.insait.io/public/logos/full-logo-light.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://cdn.insait.io/public/logos/full-logo-color.svg">
  <img alt="Insait Agent Platform" src="https://cdn.insait.io/public/logos/full-logo-light.svg" height="80">
</picture>

</br>

</br>

[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=insait-io_zendesk-voice-integration&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=insait-io_zendesk-voice-integration)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=insait-io_zendesk-voice-integration&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=insait-io_zendesk-voice-integration)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=insait-io_zendesk-voice-integration&metric=vulnerabilities)](https://sonarcloud.io/summary/new_code?id=insait-io_zendesk-voice-integration)
</div>

# Zendesk Voice Integration Server

A secure Flask-based server for automatically creating Zendesk tickets from voice call events. This application integrates with voice call services to process call data and create support tickets in Zendesk with enterprise-grade security features.

## Features

- **Automatic Ticket Creation**: Creates Zendesk tickets from voice call events
- **Enhanced Security**: Comprehensive security measures including rate limiting, input validation, and HTTPS enforcement
- **Phone Number Filtering**: Optional restriction of API access to authorized phone numbers
- **Firestore Integration**: Secure cloud-native storage for processed calls and active tickets
- **Production Ready**: Enterprise-grade security and deployment configuration

## Quick Deployment to Google Cloud Run

### Prerequisites

- Google Cloud Project with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed (for local testing)

### 1. Setup Google Cloud Environment

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

### 2. Create Firestore Database

```bash
# Create Firestore database
gcloud firestore databases create --region=us-central1
```

### 3. Create Service Account

```bash
# Create service account for the application
gcloud iam service-accounts create zendesk-voice-server \
  --display-name="Zendesk Voice Server" \
  --description="Service account for Zendesk Voice Integration Server"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:zendesk-voice-server@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:zendesk-voice-server@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 4. Store Secrets in Secret Manager

```bash
# Create secrets for Zendesk credentials
echo -n "your-domain.zendesk.com" | gcloud secrets create zendesk-domain --data-file=-
echo -n "your-email@example.com" | gcloud secrets create zendesk-email --data-file=-
echo -n "your-api-token" | gcloud secrets create zendesk-api-token --data-file=-
```

### 5. Deploy to Cloud Run

```bash
# Deploy the service
gcloud run deploy zendesk-voice-server \
  --source . \
  --platform managed \
  --region us-central1 \
  --service-account zendesk-voice-server@$PROJECT_ID.iam.gserviceaccount.com \
  --set-secrets ZENDESK_API_TOKEN=zendesk-api-token:latest,ZENDESK_EMAIL=zendesk-email:latest,ZENDESK_DOMAIN=zendesk-domain:latest \
  --set-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT_ID,FLASK_ENV=production,LOG_LEVEL=INFO \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10 \
  --timeout 300 \
  --no-allow-unauthenticated
```

### 6. Create API Access Service Account

```bash
# Create service account for API access
gcloud iam service-accounts create zendesk-api-client \
  --display-name="Zendesk API Client" \
  --description="Service account for accessing Zendesk Voice Server API"

# Grant permission to invoke Cloud Run service
gcloud run services add-iam-policy-binding zendesk-voice-server \
  --region=us-central1 \
  --member="serviceAccount:zendesk-api-client@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

# Create and download credentials file
gcloud iam service-accounts keys create zendesk-api-client-key.json \
  --iam-account=zendesk-api-client@$PROJECT_ID.iam.gserviceaccount.com
```

### 7. Send Credentials to Insait

**⚠️ IMPORTANT**: After creating the service account and downloading the JSON credentials file (`zendesk-api-client-key.json`), please send this file securely to Insait for API integration setup.

The credentials file contains the authentication keys needed to access your Cloud Run service programmatically.

## API Usage

Once deployed, your service will be available at:
```
https://zendesk-voice-server-[hash]-uc.a.run.app
```

### Authentication

All API calls require authentication using the service account:

```bash
# Authenticate with service account
gcloud auth activate-service-account --key-file=zendesk-api-client-key.json

# Generate identity token
TOKEN=$(gcloud auth print-identity-token --audiences=https://your-service-url)

# Make API call
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     https://your-service-url/health
```

### API Endpoints

- **GET** `/health` - Health check endpoint
- **POST** `/call-events` - Process voice call events and create Zendesk tickets

## Local Development

```bash
# Clone repository
git clone <repository-url>
cd zendesk-voice-integration

# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup local environment
cp env.example .env
# Edit .env with your credentials

# Download service account key for local development
gcloud iam service-accounts keys create ./config/service-account-key.json \
  --iam-account=zendesk-voice-server@$PROJECT_ID.iam.gserviceaccount.com

# Run locally
python app.py
```

## Security Features

- **Input Validation**: Comprehensive validation and sanitization of all inputs
- **Rate Limiting**: Built-in protection against abuse and DoS attacks
- **Security Headers**: Full suite of security headers for web protection
- **Data Sanitization**: Phone numbers and sensitive data are masked in logs
- **Secret Management**: Google Secret Manager integration for sensitive data
- **Authentication**: Identity token-based authentication for all API access

## Support

For technical support and integration questions, please contact the Insait development team.


