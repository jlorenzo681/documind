# 🧠 DocuMind

[![CI](https://github.com/yourusername/documind/workflows/CI/badge.svg)](https://github.com/yourusername/documind/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

> **Production-ready multi-agent AI system for enterprise document analysis**

DocuMind is an intelligent document processing platform that uses 6 specialized AI agents to analyze contracts, reports, and policies. It extracts insights, generates summaries, answers questions, and identifies compliance risks.

## 🎯 Features

- **Multi-Agent Orchestration**: 6 specialized AI agents coordinated via LangGraph
- **Document Intelligence**: Parse PDF, DOCX, and images (with OCR)
- **Advanced Summarization**: Executive and detailed summaries with map-reduce
- **RAG-Powered Q&A**: Answer questions with source citations
- **Compliance Analysis**: GDPR, contract risk detection, policy validation
- **Report Generation**: Automated PDF reports with insights
- **MLOps Pipeline**: Full CI/CD with automated LLM evaluations (ragas)
- **Production Monitoring**: Prometheus metrics + Grafana dashboards
- **Cloud-Native**: Dockerized, Kubernetes-ready, multi-cloud support

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Gateway                          │
├─────────────────────────────────────────────────────────────┤
│                   LangGraph Orchestrator                     │
├──────────┬──────────┬──────────┬──────────┬────────────────┤
│  Parser  │Summarizer│    QA    │Compliance│    Reporter    │
│  Agent   │  Agent   │  Agent   │  Agent   │     Agent      │
├──────────┴──────────┴──────────┴──────────┴────────────────┤
│   Qdrant   │   Redis   │  PostgreSQL  │       S3          │
└─────────────────────────────────────────────────────────────┘
```

## ⚡ Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/documind.git
cd documind

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"

# Copy environment configuration
cp .env.example .env
# Edit .env with your API keys
```

### Start Infrastructure

```bash
# Start Qdrant, Redis, PostgreSQL, Prometheus, Grafana
make docker-up
```

### Run the API

```bash
# Development mode with auto-reload
make run

# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Analyze a Document

```bash
# Upload a document
curl -X POST http://localhost:8000/documents \
  -F "file=@contract.pdf"

# Start analysis
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"document_id": "DOC_ID", "tasks": ["full"]}'

# Get results
curl http://localhost:8000/results/TASK_ID
```

## 📊 Tech Stack

| Category | Technologies |
|----------|-------------|
| **LLMs** | GPT-4o, Claude 3.5, Llama 3.1 |
| **Orchestration** | LangGraph, LangChain |
| **API** | FastAPI, Pydantic |
| **Vector Store** | Qdrant |
| **Storage** | PostgreSQL, Redis, S3 |
| **Monitoring** | Prometheus, Grafana, LangSmith |
| **CI/CD** | GitHub Actions, Docker |
| **Cloud** | AWS (ECS, Lambda), Azure, GCP |

## 🧪 Testing

```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run LLM evaluations
make test-eval

# Lint and type check
make lint
```

## 📈 Evaluation Metrics

Continuous evaluation with ragas framework:

| Metric | Score | Target |
|--------|-------|--------|
| Faithfulness | 0.92 | > 0.85 |
| Answer Relevancy | 0.89 | > 0.80 |
| Context Precision | 0.87 | > 0.75 |
| Context Recall | 0.91 | > 0.75 |

## 📁 Project Structure

```
documind/
├── src/documind/           # Main application
│   ├── agents/             # AI agents (parser, summarizer, qa, etc.)
│   ├── api/                # FastAPI routes
│   ├── models/             # Pydantic schemas
│   ├── monitoring/         # Metrics and logging
│   └── services/           # External service integrations
├── tests/                  # Unit, integration, and eval tests
├── infra/                  # Docker, Kubernetes, Terraform
└── .github/workflows/      # CI/CD pipelines
```

## 🚀 Deployment

### Docker

```bash
# Build image
make docker-build

# Run with all infrastructure
docker compose -f infra/docker/docker-compose.yml --profile api up
```

### AWS (ECS)

The CD pipeline automatically deploys to AWS ECS on push to `main`. See `.github/workflows/cd.yml`.

## 🔧 Configuration

Key environment variables:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `QDRANT_URL` | Qdrant vector store URL |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis cache URL |

See `.env.example` for all options.

## 📚 Documentation

- [Architecture Deep Dive](docs/architecture.md)
- [API Reference](http://localhost:8000/docs)
- [Deployment Guide](docs/deployment.md)
- [MLOps Pipeline](docs/mlops.md)

## 🗺️ Roadmap

- [ ] GraphRAG for document relationships
- [ ] Multi-modal analysis (tables, charts)
- [ ] Streaming responses (SSE)
- [ ] Fine-tuned domain models
- [ ] Multi-tenancy support

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

**Built as a showcase of production-ready Agentic AI, MLOps, and Cloud-Native deployment.**
