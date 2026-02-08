# Deploying DocuMind with Podman

This guide describes how to deploy the DocuMind stack using Podman and `podman-compose`.

## Prerequisites

- **Podman**: Ensure Podman is installed.
  ```bash
  sudo apt-get install podman
  ```
- **podman-compose**: Required for orchestration.
  ```bash
  pip install podman-compose
  ```
- **Make**: Used for convenience commands.
- **Environment**: Create `.env` file from example.
  ```bash
  cp .env.example .env
  ```

## Configuration

The Podman-specific configuration is located in `infra/docker/podman-compose.yml`. This file defines the core services:
- **Qdrant**: Vector database
- **Redis**: Caching and message broker
- **PostgreSQL**: Relational database
- **Prometheus**: Monitoring
- **Grafana**: Visualization
- **API**: The DocuMind backend service

## Running the Stack

To start the entire stack, including the API:

```bash
make run-podman
```

This command will:
1.  Pull necessary images.
2.  Build the API image if needed.
3.  Start all services in detached mode.

## Verifying Deployment

Check the status of the containers:

```bash
podman ps
```

You should see containers for `documind-api`, `documind-qdrant`, `documind-redis`, `documind-postgres`, `documind-prometheus`, and `documind-grafana`.

Verify the API is responsive:

```bash
curl http://localhost:8000/health
```

You should receive a `200 OK` response.

## Stopping the Stack

To stop all services:

```bash
make podman-down
```

---

# Deploying DocuMind to GCP

This guide describes how to deploy DocuMind to Google Cloud Platform using Cloud Run and Terraform.

## Prerequisites

- **GCP Account**: Active Google Cloud Platform account
- **GCP Project**: Create a new project or use existing one
- **Terraform**: Version 1.5.0 or higher
- **gcloud CLI**: Google Cloud SDK installed and configured

## Setup

### 1. Enable Required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  secretmanager.googleapis.com \
  compute.googleapis.com \
  servicenetworking.googleapis.com \
  vpcaccess.googleapis.com
```

### 2. Create Terraform State Bucket

```bash
gsutil mb -l us-central1 gs://documind-terraform-state
gsutil versioning set on gs://documind-terraform-state
```

### 3. Configure Workload Identity for GitHub Actions

```bash
# Create service account
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions"

# Grant necessary roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Create Workload Identity Pool
gcloud iam workload-identity-pools create "github-pool" \
  --location="global" \
  --display-name="GitHub Actions Pool"

# Create Workload Identity Provider
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# Bind service account to Workload Identity
gcloud iam service-accounts add-iam-policy-binding \
  github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/YOUR_GITHUB_USERNAME/documind"
```

### 4. Set GitHub Secrets

Add the following secrets to your GitHub repository:

- `GCP_PROJECT_ID`: Your GCP project ID
- `GCP_WORKLOAD_IDENTITY_PROVIDER`: `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider`
- `GCP_SERVICE_ACCOUNT`: `github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com`

## Deployment

### 1. Initialize Terraform

```bash
cd infra/terraform/gcp
terraform init
```

### 2. Configure Variables

Create `terraform.tfvars`:

```hcl
project_id  = "your-project-id"
region      = "us-central1"
environment = "prod"
domain_name = "api.yourdomain.com"
```

### 3. Deploy Infrastructure

```bash
terraform plan
terraform apply
```

### 4. Update Secrets

```bash
# Update API keys
echo -n '{"openai_api_key":"YOUR_KEY","anthropic_api_key":"YOUR_KEY"}' | \
  gcloud secrets versions add documind-api-keys --data-file=-
```

### 5. Deploy Application

Push to `main` branch to trigger CD pipeline:

```bash
git push origin main
```

## Verification

Check Cloud Run service:

```bash
gcloud run services describe documind-api --region us-central1
```

Test the API:

```bash
SERVICE_URL=$(gcloud run services describe documind-api \
  --region us-central1 \
  --format 'value(status.url)')
curl ${SERVICE_URL}/health
```

## Monitoring

- **Cloud Run Logs**: `gcloud run services logs read documind-api --region us-central1`
- **Cloud SQL**: Check Cloud Console for database metrics
- **Memorystore**: Monitor Redis instance in Cloud Console

## Troubleshooting

### Common Issues

#### Image Names
Ensure Artifact Registry repository exists and image names are fully qualified.

#### VPC Connectivity
Verify VPC Access Connector is created and Cloud Run service is configured to use it.

#### Secrets Access
Ensure service account has `secretmanager.secretAccessor` role.

#### Database Connection
Verify Cloud SQL instance has private IP and VPC peering is configured correctly.
