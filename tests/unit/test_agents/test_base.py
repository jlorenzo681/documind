"""Unit tests for agent base classes."""

from documind.agents.base import AgentResult


class TestAgentResult:
    """Tests for AgentResult model."""

    def test_successful_result(self):
        """Test creating a successful result."""
        result = AgentResult(
            success=True,
            data={"key": "value"},
            metadata={"agent": "test"},
        )

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.errors == []
        assert result.metadata["agent"] == "test"

    def test_failed_result(self):
        """Test creating a failed result with errors."""
        result = AgentResult(
            success=False,
            data=None,
            errors=["Error 1", "Error 2"],
        )

        assert result.success is False
        assert result.data is None
        assert len(result.errors) == 2

    def test_default_values(self):
        """Test default values are set correctly."""
        result = AgentResult(success=True)

        assert result.data is None
        assert result.errors == []
        assert result.metadata == {}
