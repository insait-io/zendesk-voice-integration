# Google Cloud Run Deployment Guide

This guide explains how to deploy the Zendesk Voice Server to Google Cloud Run.

## Prerequisites

- Google Cloud SDK installed and configured
- Docker installed locally
- Access to Google Cloud Console
- Project with billing enabled

## Setup Steps

### 1. Enable Required APIs

```bash
# Enable Cloud Run API
gcloud services enable run.googleapis.com

# Enable Container Registry API
gcloud services enable containerregistry.googleapis.com

# Enable Cloud Build API (if using Cloud Build)
gcloud services enable cloudbuild.googleapis.com
```

### 2. Configure Environment Variables

Create a `.env.yaml` file for your environment variables:

```yaml
ZENDESK_DOMAIN: "your-domain.zendesk.com"
ZENDESK_EMAIL: "your-email@example.com"
ZENDESK_API_TOKEN: "your-zendesk-api-token"
FIREBASE_DATABASE_URL: "https://your-project-default-rtdb.firebaseio.com/"
PORT: "8080"
ALLOWED_PHONE_NUMBERS: "+15551234567,+15559876543"
```

### 3. Set Up Firebase Credentials

1. Go to Google Cloud Console → IAM & Admin → Service Accounts
2. Create a new service account or use existing one
3. Download the JSON key file
4. Rename it to `firebase-credentials.json` and place it in the project root

### 4. Build and Deploy

#### Option A: Using Cloud Build (Recommended)

```bash
# Build and deploy in one command
gcloud run deploy zendesk-voice-server \
  --source . \
  --platform managed \
  --region us-central1 \
  --env-vars-file .env.yaml \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10 \
  --timeout 300
```

#### Option B: Local Docker Build

```bash
# Build the Docker image
docker build -t gcr.io/YOUR_PROJECT_ID/zendesk-voice-server .

# Push to Container Registry
docker push gcr.io/YOUR_PROJECT_ID/zendesk-voice-server

# Deploy to Cloud Run
gcloud run deploy zendesk-voice-server \
  --image gcr.io/YOUR_PROJECT_ID/zendesk-voice-server \
  --platform managed \
  --region us-central1 \
  --env-vars-file .env.yaml \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10 \
  --timeout 300
```

### 5. Configure Secrets (Alternative to .env.yaml)

For better security, use Google Secret Manager:

```bash
# Create secrets
```bash
echo -n "your-zendesk-api-token" | gcloud secrets create zendesk-api-token --data-file=-
```

# Deploy with secrets
gcloud run deploy zendesk-voice-server \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-secrets ZENDESK_API_TOKEN=zendesk-api-token:latest \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10 \
  --timeout 300
```

## Configuration Options

### Resource Allocation

- **Memory**: 1Gi (adjust based on your needs)
- **CPU**: 1 (can be set to 0.5 for cost optimization)
- **Max Instances**: 10 (prevents runaway costs)
- **Timeout**: 300 seconds (5 minutes)

### Scaling

```bash
# Configure scaling
gcloud run services update zendesk-voice-server \
  --min-instances 0 \
  --max-instances 20 \
  --concurrency 80 \
  --cpu-throttling
```

### Custom Domain

```bash
# Map custom domain
gcloud run domain-mappings create \
  --service zendesk-voice-server \
  --domain your-domain.com \
  --region us-central1
```

## Monitoring and Logging

### View Logs

```bash
# View real-time logs
gcloud logs tail --service=zendesk-voice-server

# View specific log entries
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=zendesk-voice-server"
```

### Set Up Monitoring

1. Go to Cloud Console → Monitoring
2. Create alerting policies for:
   - Error rate
   - Response time
   - Memory usage
   - CPU usage

## Security Best Practices

### 1. Use Secret Manager

Store sensitive data in Google Secret Manager instead of environment variables:

```bash
# Create secrets
gcloud secrets create zendesk-api-token --replication-policy="automatic"
gcloud secrets versions add zendesk-api-token --data-file="<(echo -n 'your-token')"
```

### 2. Enable Authentication

```bash
# Require authentication
gcloud run services update zendesk-voice-server \
  --no-allow-unauthenticated
```

### 3. Use VPC Connector (if needed)

```bash
# Create VPC connector
gcloud compute networks vpc-access connectors create zendesk-connector \
  --network default \
  --region us-central1 \
  --range 10.8.0.0/28

# Deploy with VPC connector
gcloud run deploy zendesk-voice-server \
  --source . \
  --vpc-connector zendesk-connector \
  --vpc-connector-egress all
```

## Troubleshooting

### Common Issues

1. **Build Failures**
   ```bash
   # Check build logs
   gcloud builds log BUILD_ID
   ```

2. **Runtime Errors**
   ```bash
   # Check service logs
   gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=zendesk-voice-server" --limit=50
   ```

3. **Environment Variables**
   ```bash
   # Verify environment variables
   gcloud run services describe zendesk-voice-server --format="value(spec.template.spec.containers[0].env)"
   ```

### Performance Optimization

1. **Enable CPU Throttling**
   ```bash
   gcloud run services update zendesk-voice-server --cpu-throttling
   ```

2. **Adjust Memory**
   ```bash
   gcloud run services update zendesk-voice-server --memory 2Gi
   ```

3. **Set Concurrency**
   ```bash
   gcloud run services update zendesk-voice-server --concurrency 100
   ```

## Cost Optimization

### 1. Set Resource Limits

```bash
gcloud run deploy zendesk-voice-server \
  --memory 512Mi \
  --cpu 0.5 \
  --max-instances 5
```

### 2. Use CPU Throttling

```bash
gcloud run services update zendesk-voice-server --cpu-throttling
```

### 3. Monitor Usage

```bash
# View cost breakdown
gcloud billing accounts list
gcloud billing projects describe YOUR_PROJECT_ID
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Setup Google Cloud CLI
      uses: google-github-actions/setup-gcloud@v0
      with:
        service_account_key: ${{ secrets.GCP_SA_KEY }}
        project_id: ${{ secrets.GCP_PROJECT_ID }}
    
    - name: Deploy to Cloud Run
      run: |
        gcloud run deploy zendesk-voice-server \
          --source . \
          --platform managed \
          --region us-central1 \
          --env-vars-file .env.yaml
```

## Support

For issues with Google Cloud Run:
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Run Troubleshooting](https://cloud.google.com/run/docs/troubleshooting)
- [Google Cloud Support](https://cloud.google.com/support)

For issues with this application:
- Check the application logs
- Review the main README.md file
- Create an issue in the repository 