# Tech Stack

## Language & Runtime
- Python 3.11+ (required)
- Async-first: all I/O uses `async/await`

## Core Frameworks
- **FastAPI** — REST API with Pydantic v2 for request/response validation
- **LangGraph + LangChain** — multi-agent orchestration and LLM abstractions
- **SQLAlchemy 2.0** (async) + **Alembic** — ORM and database migrations
- **Pydantic Settings** — configuration management via environment variables

## LLM Providers
- Groq (Llama 3.1/3.3 — default/free tier)
- OpenAI (GPT-4o), Anthropic (Claude 3.5)
- Local inference via Ollama and TEI (Text Embeddings Inference)
- Cohere for reranking

## Storage & Data
- **PostgreSQL** — primary database (asyncpg driver)
- **Qdrant** — vector store for embeddings
- **Redis** — caching and task queue
- **GCS / S3** — document blob storage

## Document Processing
- `pypdf`, `python-docx`, `pytesseract` + `Pillow` (OCR)

## Monitoring & Observability
- **Prometheus** + **Grafana** — metrics and dashboards
- **LangSmith** — LLM tracing
- **structlog** — structured logging via `LoggerAdapter`

## Build & Tooling
- **Hatchling** — build backend (`pyproject.toml`)
- **Ruff** — linting and formatting (line length: 100)
- **MyPy** — static type checking (`--ignore-missing-imports`)
- **Bandit** — security scanning
- **pre-commit** — enforces ruff, mypy, bandit, and file hygiene on commit

## Testing
- **pytest** + `pytest-cov` — unit and integration tests
- **Hypothesis** — property-based testing
- **ragas** — LLM evaluation metrics (faithfulness, relevance, precision, recall)

## Infrastructure
- Docker / Podman + Compose — local dev
- Kubernetes — production
- Terraform — GCP infrastructure
- GitHub Actions — CI/CD (`ci.yml`, `cd.yml`, `eval.yml`)

## Common Commands

```bash
make dev              # install dev deps + pre-commit hooks
make install          # install production deps only

make test             # all tests with coverage
make test-unit        # unit tests only
make test-integration # integration tests only
make test-eval        # ragas LLM evaluation tests

make lint             # ruff check + mypy
make format           # ruff format (auto-fix)
make security         # bandit security scan

make docker-up        # start infrastructure (Qdrant, Redis, Postgres, Prometheus, Grafana)
make docker-down      # stop infrastructure
make run              # dev server with auto-reload

make docker-build     # build Docker image
make clean            # remove build artifacts
```
