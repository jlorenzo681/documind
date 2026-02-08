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

## Troubleshooting

- **Port Conflicts**: Ensure ports 8000, 6333, 6379, 5432, 9090, and 3000 are free.

## Common Issues

### Image Names
Podman may require fully qualified image names (e.g., `docker.io/library/postgres:16-alpine`) if search registries are not configured.

### Healthchecks
If `curl` is missing in a container (like `qdrant`), use a TCP check:
```yaml
test: ["CMD-SHELL", "bash -c 'cat < /dev/tcp/localhost/6333'"]
```

### Build Errors
- **Missing README.md**: Ensure `README.md` is in the build context if `pyproject.toml` references it.
- **Package Names**: Debian package names may differ in base images (e.g., `libgdk-pixbuf-2.0-0` vs `libgdk-pixbuf2.0-0`).
