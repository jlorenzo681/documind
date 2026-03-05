"""Document Parser Agent for extracting text from various document formats."""

from pathlib import Path
from typing import Any

from documind.agents.base import BaseAgent
from documind.models.state import AgentState, DocumentChunk
from documind.monitoring import monitor_agent
from documind.utils.chunking import get_chunker


class DocumentParserAgent(BaseAgent):
    """Agent responsible for parsing documents and extracting text.

    Supports:
    - PDF files (using pypdf)
    - DOCX files (using python-docx)
    - Plain text files
    - Images with OCR (using pytesseract)
    """

    def __init__(self) -> None:
        super().__init__("parser")
        # Use structure-aware chunking — respects section headers common in legal/financial docs
        self._chunker = get_chunker("structure", chunk_size=1000)

    @monitor_agent("parser")
    async def execute(self, state: AgentState) -> AgentState:
        """Parse the document and extract text chunks."""
        self.logger.info(
            "Starting document parsing",
            document_id=state["document_id"],
            path=state["document_path"],
        )

        state = self._add_trace(state, "Starting document parsing")

        try:
            # Determine document type
            doc_path = Path(state["document_path"])
            suffix = doc_path.suffix.lower()

            # Extract raw text based on file type
            if suffix == ".pdf":
                raw_text, page_count = await self._parse_pdf(doc_path)
                doc_type = "pdf"
            elif suffix == ".docx":
                raw_text = await self._parse_docx(doc_path)
                doc_type = "docx"
            elif suffix in {".txt", ".md"}:
                raw_text = await self._parse_text(doc_path)
                doc_type = "text"
            elif suffix in {".png", ".jpg", ".jpeg", ".tiff"}:
                raw_text = await self._parse_image(doc_path)
                doc_type = "image"
            else:
                state = self._add_error(state, f"Unsupported file type: {suffix}")
                return state

            # Create chunks
            chunks = self._create_chunks(raw_text, doc_type)

            self.logger.info(
                "Document parsed successfully",
                document_id=state["document_id"],
                doc_type=doc_type,
                chunk_count=len(chunks),
            )

            state = self._add_trace(state, f"Parsed {len(chunks)} chunks from {doc_type} document")

            return {
                **state,
                "raw_text": raw_text,
                "chunks": chunks,
                "document_type": doc_type,
            }

        except Exception as e:
            self.logger.exception("Document parsing failed", error=str(e))
            state = self._add_error(state, f"Parsing failed: {str(e)}")
            return state

    async def _parse_pdf(self, path: Path) -> tuple[str, int]:
        """Parse PDF document."""
        import asyncio

        import pypdf

        def _read() -> tuple[str, int]:
            text_parts: list[str] = []
            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)
                page_count = len(reader.pages)
                for page_num, page in enumerate(reader.pages):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_parts.append(f"[Page {page_num + 1}]\n{page_text}")
            return "\n\n".join(text_parts), page_count

        return await asyncio.to_thread(_read)

    async def _parse_docx(self, path: Path) -> str:
        """Parse DOCX document."""
        import asyncio

        from docx import Document

        def _read() -> str:
            doc = Document(str(path))
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            return "\n\n".join(paragraphs)

        return await asyncio.to_thread(_read)

    async def _parse_text(self, path: Path) -> str:
        """Parse plain text file."""
        import asyncio

        return await asyncio.to_thread(path.read_text, encoding="utf-8")

    async def _parse_image(self, path: Path) -> str:
        """Parse image using OCR."""
        import asyncio

        import pytesseract
        from PIL import Image

        def _ocr() -> str:
            image = Image.open(path)
            return pytesseract.image_to_string(image)

        return await asyncio.to_thread(_ocr)

    def _create_chunks(self, text: str, doc_type: str) -> list[DocumentChunk]:
        """Split text into chunks using structure-aware chunking."""
        import re

        raw_chunks = self._chunker.chunk(text)
        result: list[DocumentChunk] = []

        for index, raw in enumerate(raw_chunks):
            content = raw["content"].strip()
            if not content:
                continue

            # Extract page number from [Page N] markers embedded by PDF parser
            page: int | None = None
            match = re.search(r"\[Page (\d+)\]", content)
            if match:
                page = int(match.group(1))

            result.append(
                DocumentChunk(
                    content=content,
                    page=page,
                    chunk_index=index,
                    metadata={
                        "doc_type": doc_type,
                        "char_start": raw.get("char_start", 0),
                        "char_end": raw.get("char_end", len(content)),
                        "section_header": raw.get("header"),
                    },
                )
            )

        return result

    def get_tools(self) -> list[Any]:
        """Return tools available to this agent."""
        return []  # Parser doesn't use external tools
