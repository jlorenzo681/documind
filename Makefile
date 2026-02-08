.PHONY: install dev test lint format clean docker-up docker-down run

# Install production dependencies
install:
	pip install -e .

# Install development dependencies
dev:
	pip install -e ".[dev]"
	pre-commit install

# Run all tests
test:
	pytest tests/ -v --cov=src/documind --cov-report=term-missing

# Run unit tests only
test-unit:
	pytest tests/unit/ -v

# Run integration tests only
test-integration:
	pytest tests/integration/ -v

# Run LLM evaluation tests
test-eval:
	python tests/eval/run_evals.py

# Lint code
lint:
	ruff check src/ tests/
	mypy src/

# Format code
format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

# Security scan
security:
	bandit -r src/ -c pyproject.toml

# Docker/Podman configuration
DOCKER ?= docker
# Detect podman
ifneq ($(shell which podman 2>/dev/null),)
	DOCKER_COMPOSE ?= podman-compose
	COMPOSE_FILE ?= infra/docker/podman-compose.yml
else
	DOCKER_COMPOSE ?= docker compose
	COMPOSE_FILE ?= infra/docker/docker-compose.yml
endif

# Start Docker/Podman development environment
docker-up:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) up -d

# Stop Docker/Podman development environment
docker-down:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) down

# Explicit Podman commands
podman-up:
	podman-compose -f infra/docker/podman-compose.yml up -d

podman-down:
	podman-compose -f infra/docker/podman-compose.yml down

# Run the API server locally
run:
	uvicorn documind.main:app --reload --host 0.0.0.0 --port 8000

# Run with Docker
run-docker:
	docker compose -f infra/docker/docker-compose.yml --profile api up

# Run with Podman
run-podman:
	podman-compose -f infra/docker/podman-compose.yml --profile api up -d
	@echo "Services are starting. The API will be available at http://localhost:8000/health"

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Build Docker image
docker-build:
	docker build -t documind:latest -f infra/docker/Dockerfile .

# Generate API documentation
docs:
	@echo "API docs available at http://localhost:8000/docs when server is running"
