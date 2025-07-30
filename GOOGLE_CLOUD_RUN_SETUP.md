# Google Cloud Run Deployment Guide

This guide explains how to deploy the Zendesk Voice Server to Google Cloud Run with Firestore integration.

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

# Enable Firestore API
gcloud services enable firestore.googleapis.com

# Enable Secret Manager API (REQUIRED for environment secrets)
gcloud services enable secretmanager.googleapis.com

# Enable Cloud Resource Manager API (for project management)
gcloud services enable cloudresourcemanager.googleapis.com

# Enable all APIs at once (alternative command)
gcloud services enable \
  run.googleapis.com \
  containerregistry.googleapis.com \
  cloudbuild.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  cloudresourcemanager.googleapis.com
```

### 2. Set Up Firestore Database

Create and configure Firestore database:

```bash
# Create Firestore database in native mode (recommended)
gcloud firestore databases create --location=us-central1

# Alternative: Create in a specific location closer to your users
# gcloud firestore databases create --location=europe-west1

# Verify Firestore is enabled
gcloud firestore databases list
```

**Important Firestore Setup Notes:**
- Choose your region carefully - this cannot be changed later
- Native mode is recommended for new applications (vs Datastore mode)
- Firestore automatically creates indexes for basic queries
- Consider your data location requirements for compliance

### 3. Configure Service Account and Permissions

```bash
# Create a service account for the application
gcloud iam service-accounts create zendesk-voice-server \
    --display-name="Zendesk Voice Server" \
    --description="Service account for Zendesk Voice Integration"

# Grant necessary permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:zendesk-voice-server@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

# Download service account key (for local development)
gcloud iam service-accounts keys create service-account-key.json \
    --iam-account=zendesk-voice-server@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 4. Configure Environment Variables

Create a `.env.yaml` file for your environment variables:

```yaml
ZENDESK_DOMAIN: "your-domain.zendesk.com"
ZENDESK_EMAIL: "your-email@example.com"
ZENDESK_API_TOKEN: "your-zendesk-api-token"
GOOGLE_CLOUD_PROJECT: "your-gcp-project-id"
FLASK_ENV: "production"
ALLOWED_PHONE_NUMBERS: "+15551234567,+15559876543"
LOG_LEVEL: "INFO"
```

**Note:** The `PORT` environment variable is automatically set by Google Cloud Run and should not be manually configured.

### 5. Build and Deploy

#### Option A: Using Cloud Build (Recommended)

```bash
# Build and deploy in one command
gcloud run deploy zendesk-voice-server \
  --source . \
  --platform managed \
  --region us-central1 \
  --env-vars-file .env.yaml \
  --service-account zendesk-voice-server@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10 \
  --timeout 300 \
  --no-allow-unauthenticated \
  --ingress all
```

#### Option B: Local Docker Build

```bash
# Set your project ID
export PROJECT_ID=your-gcp-project-id

# Build the Docker image
docker build -t gcr.io/$PROJECT_ID/zendesk-voice-server .

# Push to Container Registry
docker push gcr.io/$PROJECT_ID/zendesk-voice-server

# Deploy to Cloud Run
gcloud run deploy zendesk-voice-server \
  --image gcr.io/$PROJECT_ID/zendesk-voice-server \
  --platform managed \
  --region us-central1 \
  --env-vars-file .env.yaml \
  --service-account zendesk-voice-server@$PROJECT_ID.iam.gserviceaccount.com \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10 \
  --timeout 300 \
  --no-allow-unauthenticated \
  --ingress all
```

### 6. Configure Secrets (Enhanced Security)

For better security, use Google Secret Manager instead of environment variables:

```bash
# Create secrets in Secret Manager
echo -n "your-zendesk-api-token" | gcloud secrets create zendesk-api-token --data-file=-
echo -n "your-email@example.com" | gcloud secrets create zendesk-email --data-file=-
echo -n "your-domain.zendesk.com" | gcloud secrets create zendesk-domain --data-file=-

# Grant secret access to service account
gcloud secrets add-iam-policy-binding zendesk-api-token \
    --member="serviceAccount:zendesk-voice-server@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding zendesk-email \
    --member="serviceAccount:zendesk-voice-server@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding zendesk-domain \
    --member="serviceAccount:zendesk-voice-server@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Deploy with secrets
gcloud run deploy zendesk-voice-server \
  --source . \
  --platform managed \
  --region us-central1 \
  --service-account zendesk-voice-server@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --set-secrets ZENDESK_API_TOKEN=zendesk-api-token:latest,ZENDESK_EMAIL=zendesk-email:latest,ZENDESK_DOMAIN=zendesk-domain:latest \
  --set-env-vars GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,FLASK_ENV=production,LOG_LEVEL=INFO \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10 \
  --timeout 300 \
  --no-allow-unauthenticated
```

### 7. Create Service Account for API Access

Create a service account that can be used to trigger the Cloud Run service from external systems or for testing:

```bash
# Create service account for API access
gcloud iam service-accounts create zendesk-api-client \
  --display-name="Zendesk API Client" \
  --description="Service account for accessing Zendesk Voice Server API"

# Grant the service account permission to invoke the Cloud Run service
gcloud run services add-iam-policy-binding zendesk-voice-server \
  --region=us-central1 \
  --member="serviceAccount:zendesk-api-client@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

# Create and download a key for the service account (for external systems)
gcloud iam service-accounts keys create zendesk-api-client-key.json \
  --iam-account=zendesk-api-client@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Store the key securely and use it to generate identity tokens
# Example: Generate an identity token for API calls
gcloud auth activate-service-account --key-file=zendesk-api-client-key.json
gcloud auth print-identity-token --audiences=https://zendesk-voice-server-f4sffiqfgq-uc.a.run.app
```

**Usage Example:**
```bash
# Get identity token
TOKEN=$(gcloud auth print-identity-token --audiences=https://zendesk-voice-server-f4sffiqfgq-uc.a.run.app)

# Make authenticated API call
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     https://zendesk-voice-server-f4sffiqfgq-uc.a.run.app/health
```

### Alternative: Make Service Public (for Webhooks)

If you need the service to be accessible by external webhooks (like Zendesk Voice), you can make it public:

```bash
# WARNING: This removes authentication requirements
# Only do this if you have application-level security measures

gcloud run services add-iam-policy-binding zendesk-voice-server \
  --region=us-central1 \
  --member="allUsers" \
  --role="roles/run.invoker"

# Your service will then be accessible at:
# https://zendesk-voice-server-f4sffiqfgq-uc.a.run.app
```

**Security Note**: When making the service public, ensure your application has proper:
- Input validation
- Rate limiting (already implemented with flask-limiter)
- Request signature verification
- IP allowlisting if possible

### 8. Set Up Firestore Security Rules

Create security rules for Firestore:

```bash
# Create firestore.rules file
cat > firestore.rules << EOF
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Only allow authenticated service account to read/write
    match /{document=**} {
      allow read, write: if request.auth != null && request.auth.token.email.matches('.*@YOUR_PROJECT_ID.iam.gserviceaccount.com');
    }
  }
}
EOF

# Deploy security rules
gcloud firestore deploy --rules firestore.rules
```

## Configuration Options

### Resource Allocation

- **Memory**: 1Gi (adjust based on your needs, minimum 512Mi)
- **CPU**: 1 (can be set to 0.5 for cost optimization)
- **Max Instances**: 10 (prevents runaway costs)
- **Timeout**: 300 seconds (5 minutes)
- **Concurrency**: 80 requests per instance (default)

### Scaling and Performance

```bash
# Configure auto-scaling
gcloud run services update zendesk-voice-server \
  --min-instances 0 \
  --max-instances 20 \
  --concurrency 80 \
  --cpu-throttling

# For high-traffic scenarios
gcloud run services update zendesk-voice-server \
  --min-instances 2 \
  --max-instances 50 \
  --concurrency 100 \
  --memory 2Gi
```

### Custom Domain and SSL

```bash
# Map custom domain (requires domain ownership verification)
gcloud run domain-mappings create \
  --service zendesk-voice-server \
  --domain your-api.example.com \
  --region us-central1

# SSL certificates are automatically provisioned by Google
```

### Firestore Database Management

```bash
# List Firestore collections (for debugging)
gcloud firestore collections list

# Export Firestore data (for backup)
gcloud firestore export gs://your-backup-bucket/firestore-backup \
  --collection-ids=processed_calls,active_tickets

# Import Firestore data (for restoration)
gcloud firestore import gs://your-backup-bucket/firestore-backup/[EXPORT_PREFIX]
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
# Create secrets with proper naming
gcloud secrets create zendesk-api-token --replication-policy="automatic"
gcloud secrets versions add zendesk-api-token --data-file="<(echo -n 'your-token')"

# List secrets
gcloud secrets list

# Access secret version
gcloud secrets versions access latest --secret="zendesk-api-token"
```

### 2. Enable Authentication and Authorization

```bash
# Require authentication (recommended for production)
gcloud run services update zendesk-voice-server \
  --no-allow-unauthenticated

# Create specific IAM bindings for authorized users/services
gcloud run services add-iam-policy-binding zendesk-voice-server \
  --member="user:admin@yourcompany.com" \
  --role="roles/run.invoker" \
  --region us-central1
```

### 3. Network Security

```bash
# Create VPC connector for private networking (if needed)
gcloud compute networks vpc-access connectors create zendesk-connector \
  --network default \
  --region us-central1 \
  --range 10.8.0.0/28 \
  --min-instances 2 \
  --max-instances 3

# Deploy with VPC connector and egress control
gcloud run deploy zendesk-voice-server \
  --source . \
  --vpc-connector zendesk-connector \
  --vpc-connector-egress private-ranges-only \
  --ingress internal-and-cloud-load-balancing
```

### 4. Enhanced Monitoring and Alerting

```bash
# Enable audit logs
gcloud logging sinks create zendesk-voice-audit-sink \
  bigquery.googleapis.com/projects/YOUR_PROJECT_ID/datasets/audit_logs \
  --log-filter='resource.type="cloud_run_revision" AND resource.labels.service_name="zendesk-voice-server"'

# Create alerting policy for errors
gcloud alpha monitoring policies create --policy-from-file=monitoring-policy.yaml
```

### 5. Firestore Security

- Use Firestore security rules to restrict access
- Enable audit logging for Firestore operations
- Implement proper indexing for performance
- Regular backup of critical data

## Troubleshooting

### Common Issues

1. **Deployment Error: Secret Manager API Not Enabled**
   ```
   ERROR: Secret Manager API has not been used in project [PROJECT_ID] before or it is disabled
   ```
   
   **Solution**: Enable the Secret Manager API and wait a few minutes for propagation.
   
   ```bash
   # Enable Secret Manager API
   gcloud services enable secretmanager.googleapis.com
   
   # Check if API is enabled
   gcloud services list --enabled --filter="name:secretmanager.googleapis.com"
   
   # Wait 2-3 minutes then retry deployment
   ```

2. **Deployment Error: Reserved ENV Names (PORT)**
   ```
   ERROR: spec.template.spec.containers[0].env: The following reserved env names were provided: PORT
   ```
   
   **Solution**: Remove `PORT` from your environment variables. Cloud Run automatically sets the PORT environment variable.
   
   ```bash
   # ❌ Incorrect - Do not set PORT
   --set-env-vars PORT=8080,FLASK_ENV=production
   
   # ✅ Correct - Let Cloud Run set PORT automatically
   --set-env-vars FLASK_ENV=production
   ```

2. **Build Failures**
   ```bash
   # Check build logs
   gcloud builds log BUILD_ID
   ```

3. **Runtime Errors**
   ```bash
   # Check service logs
   gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=zendesk-voice-server" --limit=50
   ```

4. **Environment Variables**
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