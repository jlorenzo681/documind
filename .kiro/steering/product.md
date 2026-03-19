# DocuMind — Product Overview

DocuMind is a production-ready multi-agent AI system for enterprise document analysis. It processes contracts, reports, and policies using 6 specialized AI agents coordinated via LangGraph.

## Core Capabilities

- **Document Parsing**: PDF, DOCX, and image (OCR) ingestion
- **Summarization**: Executive and detailed summaries via map-reduce
- **RAG Q&A**: Question answering with source citations over document content
- **Compliance Analysis**: GDPR, contract risk detection, policy validation
- **Report Generation**: Automated PDF reports with extracted insights
- **MLOps**: LLM evaluation pipeline using ragas, CI/CD with automated evals

## Agent Pipeline

Documents flow through a LangGraph orchestrator that routes to 6 agents:
`Parser → Summarizer → QA → Compliance → Reporter`

## Users / Deployment Context

Enterprise users via REST API (FastAPI), a Streamlit chatbot frontend, or a Python SDK. Deployed on GCP Cloud Run with Kubernetes support.
