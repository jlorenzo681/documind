"""Pytest configuration for DocuMind tests."""


import pytest


@pytest.fixture
def sample_text() -> str:
    """Sample document text for testing."""
    return """
    SERVICE AGREEMENT

    This Service Agreement ("Agreement") is entered into as of January 1, 2026,
    by and between ACME Corporation ("Provider") and Client Company ("Client").

    1. SERVICES
    Provider agrees to provide the following services:
    - Document analysis and processing
    - Data extraction and summarization
    - Compliance checking

    2. TERM
    This Agreement shall commence on the Effective Date and continue for
    a period of one (1) year, unless terminated earlier.

    3. COMPENSATION
    Client agrees to pay Provider a monthly fee of $5,000 for the services.
    Payment is due within 30 days of invoice receipt.

    4. CONFIDENTIALITY
    Both parties agree to maintain the confidentiality of any proprietary
    information shared during the course of this Agreement.

    5. LIMITATION OF LIABILITY
    In no event shall either party be liable for any indirect, incidental,
    special, or consequential damages.

    6. TERMINATION
    Either party may terminate this Agreement with 30 days written notice.

    7. GOVERNING LAW
    This Agreement shall be governed by the laws of the State of California.

    IN WITNESS WHEREOF, the parties have executed this Agreement.

    ACME Corporation
    By: _____________________
    Name: John Smith
    Title: CEO

    Client Company
    By: _____________________
    Name: Jane Doe
    Title: COO
    """


@pytest.fixture
def sample_questions() -> list[str]:
    """Sample questions for QA testing."""
    return [
        "What is the monthly fee for services?",
        "How long is the agreement term?",
        "What happens if confidentiality is breached?",
    ]


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing without API calls."""

    class MockResponse:
        content = "This is a mock LLM response for testing purposes."

    return MockResponse()
