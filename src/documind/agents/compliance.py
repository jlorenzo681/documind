"""Compliance Agent for detecting risks and policy violations."""

from typing import Any

from documind.agents.base import BaseAgent
from documind.models.state import AgentState
from documind.monitoring import monitor_agent


class ComplianceAgent(BaseAgent):
    """Agent responsible for compliance checking and risk assessment.

    Checks for:
    - GDPR compliance issues
    - Contract risk clauses
    - Policy violations
    - Missing required elements
    """

    COMPLIANCE_RULES = {
        "gdpr": [
            "data retention",
            "personal data",
            "data processing",
            "consent",
            "data subject rights",
            "data protection officer",
            "privacy policy",
        ],
        "contract_risks": [
            "unlimited liability",
            "automatic renewal",
            "unilateral modification",
            "exclusive jurisdiction",
            "waiver of rights",
            "non-compete",
            "confidentiality breach",
        ],
        "required_clauses": [
            "termination",
            "dispute resolution",
            "force majeure",
            "indemnification",
            "limitation of liability",
        ],
    }

    def __init__(self) -> None:
        super().__init__("compliance")

    @monitor_agent("compliance")
    async def execute(self, state: AgentState) -> AgentState:
        """Perform compliance analysis on the document."""
        self.logger.info(
            "Starting compliance check",
            document_id=state["document_id"],
            doc_type=state.get("document_type"),
        )

        state = self._add_trace(state, "Starting compliance analysis")

        try:
            # Combine document text
            full_text = "\n\n".join(c["content"] for c in state["chunks"])

            # Run compliance checks
            issues = await self._check_compliance(full_text, state)

            # Calculate risk score
            risk_score, risk_level = self._calculate_risk_score(issues)

            # Generate recommendations
            recommendations = self._generate_recommendations(issues)

            compliance_report = {
                "overall_risk_score": risk_score,
                "risk_level": risk_level,
                "issues": issues,
                "recommendations": recommendations,
                "clauses_analyzed": len(state["chunks"]),
            }

            self.logger.info(
                "Compliance check completed",
                document_id=state["document_id"],
                risk_score=risk_score,
                risk_level=risk_level,
                issue_count=len(issues),
            )

            state = self._add_trace(
                state, f"Compliance check completed: {risk_level} risk ({risk_score})"
            )

            return {**state, "compliance_report": compliance_report}

        except Exception as e:
            self.logger.exception("Compliance check failed", error=str(e))
            state = self._add_error(state, f"Compliance check failed: {str(e)}")
            return state

    async def _check_compliance(self, text: str, state: AgentState) -> list[dict[str, Any]]:
        """Check document for compliance issues using LLM."""
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI

        from documind.config import get_settings

        settings = get_settings()

        llm = ChatOpenAI(
            model=settings.llm.default_model,
            api_key=settings.llm.openai_api_key.get_secret_value(),
            temperature=0.1,
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an expert legal and compliance analyst.
            Analyze the document for potential risks and compliance issues.

            Focus on:
            1. GDPR and data protection concerns
            2. Contract risk clauses (unlimited liability, auto-renewal, etc.)
            3. Missing standard clauses
            4. Ambiguous or problematic language

            For each issue found, provide:
            - category: The type of issue (gdpr, contract_risk, missing_clause, ambiguity)
            - severity: high, medium, or low
            - description: Brief description of the issue
            - location: Where in the document (if identifiable)
            - excerpt: Relevant text excerpt (max 100 chars)

            Return as JSON array of issues. If no issues, return empty array [].""",
                ),
                ("user", "{document}"),
            ]
        )

        chain = prompt | llm
        result = await chain.ainvoke({"document": text[:15000]})  # Limit context

        # Parse result
        import json

        try:
            issues = json.loads(result.content)
            if not isinstance(issues, list):
                issues = []
        except json.JSONDecodeError:
            # Fallback: perform keyword-based detection
            issues = self._keyword_based_detection(text)

        return issues

    def _keyword_based_detection(self, text: str) -> list[dict[str, Any]]:
        """Fallback keyword-based compliance detection."""
        issues: list[dict[str, Any]] = []
        text_lower = text.lower()

        # Check for risk keywords
        for keyword in self.COMPLIANCE_RULES["contract_risks"]:
            if keyword in text_lower:
                issues.append(
                    {
                        "category": "contract_risk",
                        "severity": "medium",
                        "description": f"Document contains '{keyword}' clause",
                        "location": "detected via keyword search",
                        "excerpt": keyword,
                    }
                )

        # Check for missing clauses (if it looks like a contract)
        if "agreement" in text_lower or "contract" in text_lower:
            for clause in self.COMPLIANCE_RULES["required_clauses"]:
                if clause not in text_lower:
                    issues.append(
                        {
                            "category": "missing_clause",
                            "severity": "low",
                            "description": f"Missing '{clause}' clause",
                            "location": "document",
                            "excerpt": "",
                        }
                    )

        return issues

    def _calculate_risk_score(self, issues: list[dict[str, Any]]) -> tuple[float, str]:
        """Calculate overall risk score from issues."""
        if not issues:
            return 0.0, "low"

        severity_weights = {"high": 30, "medium": 15, "low": 5}

        total_score = sum(severity_weights.get(issue.get("severity", "low"), 5) for issue in issues)

        # Cap at 100
        risk_score = min(total_score, 100)

        # Determine risk level
        if risk_score >= 60:
            risk_level = "high"
        elif risk_score >= 30:
            risk_level = "medium"
        else:
            risk_level = "low"

        return risk_score, risk_level

    def _generate_recommendations(self, issues: list[dict[str, Any]]) -> list[str]:
        """Generate recommendations based on issues found."""
        recommendations: list[str] = []

        categories = {issue.get("category") for issue in issues}

        if "gdpr" in categories:
            recommendations.append("Review data protection clauses with legal counsel")
            recommendations.append("Ensure GDPR compliance documentation is complete")

        if "contract_risk" in categories:
            recommendations.append("Negotiate high-risk clauses before signing")
            recommendations.append("Consider adding liability caps and limitations")

        if "missing_clause" in categories:
            recommendations.append("Add standard protective clauses before finalizing")

        if not recommendations:
            recommendations.append("Document appears compliant - standard review recommended")

        return recommendations

    def get_tools(self) -> list[Any]:
        """Return tools available to this agent."""
        return []
