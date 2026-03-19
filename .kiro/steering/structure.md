# Project Structure

```
documind/
├── src/documind/
│   ├── agents/          # AI agents — all inherit from BaseAgent
│   │   ├── base.py      # Abstract BaseAgent class (execute method contract)
│   │   ├── orchestrator.py
│   │   ├── parser.py
│   │   ├── summarizer.py
│   │   ├── qa.py
│   │   ├── compliance.py
│   │   └── reporter.py
│   ├── api/
│   │   ├── routes/      # FastAPI routers (health, documents, analysis, results)
│   │   ├── middleware.py # Auth (API key), rate limiting, request logging
│   │   ├── dependencies.py
│   │   └── task_store.py # Redis-backed async task storage
│   ├── db/
│   │   ├── models.py    # SQLAlchemy models (Document, Analysis, AnalysisResult)
│   │   ├── base.py      # Async engine setup
│   │   └── repositories/ # Data access layer
│   ├── models/
│   │   ├── schemas.py   # Pydantic request/response schemas
│   │   └── state.py     # LangGraph AgentState (TypedDict)
│   ├── services/        # Singleton service wrappers
│   │   ├── llm.py       # LLM service with model routing
│   │   ├── vectorstore.py
│   │   ├── embeddings.py
│   │   ├── cache.py     # Redis
│   │   ├── database.py
│   │   └── storage.py   # GCS/S3
│   ├── monitoring/
│   │   ├── metrics.py   # Prometheus metrics
│   │   └── logging.py   # structlog LoggerAdapter
│   ├── utils/
│   │   └── chunking.py  # Chunking strategies (recursive, semantic, structure-aware)
│   ├── frontend/
│   │   └── chatbot.py   # Streamlit UI
│   ├── config.py        # Pydantic Settings (nested: LLMSettings, VectorStoreSettings, etc.)
│   └── main.py          # FastAPI app factory + lifespan handler
├── tests/
│   ├── unit/            # Per-component tests (agents, API routes)
│   ├── integration/     # Full workflow tests (requires live services)
│   ├── eval/            # ragas LLM quality evaluations
│   └── conftest.py      # Shared pytest fixtures
├── alembic/             # DB migration scripts
│   └── versions/
├── infra/
│   ├── docker/          # Compose files, Prometheus, Grafana configs
│   ├── k8s/             # Kubernetes manifests
│   └── terraform/       # GCP infrastructure
├── docs/
│   ├── architecture.md
│   └── deployment.md
├── .github/workflows/   # ci.yml, cd.yml, eval.yml
├── Makefile
├── pyproject.toml       # Dependencies, ruff/mypy/pytest config
├── alembic.ini
└── .env.example
```

## Key Conventions

- All source code lives under `src/documind/` (src layout)
- New agents go in `src/documind/agents/` and must subclass `BaseAgent`
- New API endpoints go in `src/documind/api/routes/` as separate router modules
- Services follow the singleton pattern with a `get_<service>()` getter function
- Agent state is defined in `models/state.py` as `TypedDict` — add fields there for new state
- Pydantic schemas for API I/O go in `models/schemas.py`
- Configuration is managed via `config.py` using nested `pydantic-settings` classes; never hardcode secrets
- Migrations are managed with Alembic — always generate a migration when changing DB models
