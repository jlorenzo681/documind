"""Report Generator Agent for creating PDF/DOCX reports."""

from datetime import datetime
from pathlib import Path
from typing import Any

from documind.agents.base import BaseAgent
from documind.models.state import AgentState
from documind.monitoring import monitor_agent


class ReportGeneratorAgent(BaseAgent):
    """Agent responsible for generating analysis reports.

    Outputs:
    - PDF executive reports
    - Detailed analysis documents
    - Customizable templates
    """

    def __init__(self, output_dir: str = "/tmp/documind/reports") -> None:
        super().__init__("reporter")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @monitor_agent("reporter")
    async def execute(self, state: AgentState) -> AgentState:
        """Generate the final analysis report."""
        self.logger.info(
            "Starting report generation",
            document_id=state["document_id"],
        )

        state = self._add_trace(state, "Starting report generation")

        try:
            # Generate PDF report
            report_path = await self._generate_pdf_report(state)

            self.logger.info(
                "Report generated",
                document_id=state["document_id"],
                report_path=str(report_path),
            )

            state = self._add_trace(state, f"Report generated: {report_path.name}")

            return {**state, "final_report_path": str(report_path)}

        except Exception as e:
            self.logger.exception("Report generation failed", error=str(e))
            state = self._add_error(state, f"Report generation failed: {str(e)}")
            return state

    async def _generate_pdf_report(self, state: AgentState) -> Path:
        """Generate a PDF report from analysis results."""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        # Create output path
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"report_{state['task_id']}_{timestamp}.pdf"

        # Setup document
        doc = SimpleDocTemplate(
            str(report_path),
            pagesize=letter,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch,
        )

        # Styles
        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        heading_style = styles["Heading1"]
        normal_style = styles["Normal"]

        # Build content
        content: list[Any] = []

        # Title
        content.append(Paragraph("DocuMind Analysis Report", title_style))
        content.append(Spacer(1, 0.5 * inch))

        # Document info
        content.append(Paragraph("Document Information", heading_style))
        info_data = [
            ["Document ID:", state["document_id"]],
            ["Task ID:", state["task_id"]],
            ["Document Type:", state.get("document_type", "Unknown")],
            ["Generated:", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")],
        ]
        info_table = Table(info_data, colWidths=[2 * inch, 4 * inch])
        info_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        content.append(info_table)
        content.append(Spacer(1, 0.3 * inch))

        # Summary section
        if state.get("summary"):
            content.append(Paragraph("Executive Summary", heading_style))
            summary = state["summary"]
            content.append(
                Paragraph(
                    summary.get("executive_summary", "No summary available"),
                    normal_style,
                )
            )
            content.append(Spacer(1, 0.2 * inch))

            # Key points
            if summary.get("key_points"):
                content.append(Paragraph("Key Points", styles["Heading2"]))
                for point in summary["key_points"][:10]:  # Limit to 10
                    content.append(Paragraph(f"• {point}", normal_style))
                content.append(Spacer(1, 0.2 * inch))

        # Compliance section
        if state.get("compliance_report"):
            content.append(Paragraph("Compliance Analysis", heading_style))
            compliance = state["compliance_report"]

            # Risk indicator
            risk_level = compliance.get("risk_level", "unknown")
            risk_color = {
                "low": colors.green,
                "medium": colors.orange,
                "high": colors.red,
            }.get(risk_level, colors.gray)

            content.append(
                Paragraph(
                    f"Overall Risk: <b>{risk_level.upper()}</b> "
                    f"(Score: {compliance.get('overall_risk_score', 0)}/100)",
                    ParagraphStyle(
                        "Risk",
                        parent=normal_style,
                        textColor=risk_color,
                    ),
                )
            )
            content.append(Spacer(1, 0.2 * inch))

            # Issues
            issues = compliance.get("issues", [])
            if issues:
                content.append(Paragraph("Issues Found", styles["Heading2"]))
                for issue in issues[:15]:  # Limit
                    severity = issue.get("severity", "unknown")
                    content.append(
                        Paragraph(
                            f"• [{severity.upper()}] {issue.get('description', '')}",
                            normal_style,
                        )
                    )
                content.append(Spacer(1, 0.2 * inch))

            # Recommendations
            recommendations = compliance.get("recommendations", [])
            if recommendations:
                content.append(Paragraph("Recommendations", styles["Heading2"]))
                for rec in recommendations:
                    content.append(Paragraph(f"• {rec}", normal_style))

        # Q&A section
        if state.get("qa_results"):
            content.append(Spacer(1, 0.3 * inch))
            content.append(Paragraph("Questions & Answers", heading_style))
            for qa in state["qa_results"]:
                content.append(
                    Paragraph(
                        f"<b>Q:</b> {qa.get('question', '')}",
                        normal_style,
                    )
                )
                content.append(
                    Paragraph(
                        f"<b>A:</b> {qa.get('answer', '')}",
                        normal_style,
                    )
                )
                content.append(Spacer(1, 0.1 * inch))

        # Build PDF
        doc.build(content)

        return report_path

    def get_tools(self) -> list[Any]:
        """Return tools available to this agent."""
        return []
