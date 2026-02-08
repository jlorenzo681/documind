"""Document Parser Agent for extracting text from various document formats."""

from pathlib import Path
from typing import Any

from documind.agents.base import BaseAgent
from documind.models.state import AgentState, DocumentChunk
from documind.monitoring import monitor_agent


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
        self.chunk_size = 1000
        self.chunk_overlap = 200

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
                page_count = None
            elif suffix in {".txt", ".md"}:
                raw_text = await self._parse_text(doc_path)
                doc_type = "text"
                page_count = None
            elif suffix in {".png", ".jpg", ".jpeg", ".tiff"}:
                raw_text = await self._parse_image(doc_path)
                doc_type = "image"
                page_count = None
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
        import pypdf

        text_parts: list[str] = []

        with open(path, "rb") as f:
            reader = pypdf.PdfReader(f)
            page_count = len(reader.pages)

            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_parts.append(f"[Page {page_num + 1}]\n{page_text}")

        return "\n\n".join(text_parts), page_count

    async def _parse_docx(self, path: Path) -> str:
        """Parse DOCX document."""
        from docx import Document

        doc = Document(str(path))
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(paragraphs)

    async def _parse_text(self, path: Path) -> str:
        """Parse plain text file."""
        return path.read_text(encoding="utf-8")

    async def _parse_image(self, path: Path) -> str:
        """Parse image using OCR."""
        import pytesseract
        from PIL import Image

        image = Image.open(path)
        text = pytesseract.image_to_string(image)
        return text

    def _create_chunks(self, text: str, doc_type: str) -> list[DocumentChunk]:
        """Split text into overlapping chunks."""
        chunks: list[DocumentChunk] = []

        # Simple character-based chunking
        # TODO: Implement semantic chunking
        start = 0
        chunk_index = 0

        while start < len(text):
            end = start + self.chunk_size

            # Try to break at sentence or paragraph boundary
            if end < len(text):
                # Look for paragraph break
                para_break = text.rfind("\n\n", start, end)
                if para_break > start + self.chunk_size // 2:
                    end = para_break + 2
                else:
                    # Look for sentence break
                    sentence_break = text.rfind(". ", start, end)
                    if sentence_break > start + self.chunk_size // 2:
                        end = sentence_break + 2

            chunk_content = text[start:end].strip()

            if chunk_content:
                # Try to extract page number if present
                page = None
                if "[Page" in chunk_content:
                    import re

                    match = re.search(r"\[Page (\d+)\]", chunk_content)
                    if match:
                        page = int(match.group(1))

                chunks.append(
                    DocumentChunk(
                        content=chunk_content,
                        page=page,
                        chunk_index=chunk_index,
                        metadata={"doc_type": doc_type, "char_start": start},
                    )
                )
                chunk_index += 1

            start = end - self.chunk_overlap

        return chunks

    def get_tools(self) -> list[Any]:
        """Return tools available to this agent."""
        return []  # Parser doesn't use external tools
