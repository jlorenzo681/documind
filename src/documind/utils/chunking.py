"""Advanced chunking strategies for document processing."""

from typing import Any

from documind.monitoring import LoggerAdapter

logger = LoggerAdapter("utils.chunking")


class ChunkingStrategy:
    """Base class for chunking strategies."""

    def chunk(self, text: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Split text into chunks.

        Args:
            text: Text to chunk

        Returns:
            List of chunks with content and metadata
        """
        raise NotImplementedError


class RecursiveCharacterChunker(ChunkingStrategy):
    """Recursive character-based chunking with smart boundaries."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: list[str] | None = None,
    ) -> None:
        """Initialize the chunker.

        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
            separators: List of separators to try (in order)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or [
            "\n\n",  # Paragraphs
            "\n",  # Lines
            ". ",  # Sentences
            ", ",  # Clauses
            " ",  # Words
            "",  # Characters
        ]

    def chunk(self, text: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Split text using recursive character strategy."""
        return self._split_text(text, self.separators)

    def _split_text(self, text: str, separators: list[str]) -> list[dict[str, Any]]:
        """Recursively split text using separators."""
        chunks: list[dict[str, Any]] = []

        if not text:
            return chunks

        separator = separators[0] if separators else ""
        remaining_separators = separators[1:] if len(separators) > 1 else []

        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)

        current_chunk = ""
        current_start = 0

        for i, split in enumerate(splits):
            piece = split if not separator else split + separator
            piece = piece.rstrip(separator) if i == len(splits) - 1 else piece

            if len(current_chunk) + len(piece) <= self.chunk_size:
                current_chunk += piece
            else:
                if current_chunk:
                    chunks.append(
                        {
                            "content": current_chunk.strip(),
                            "char_start": current_start,
                            "char_end": current_start + len(current_chunk),
                        }
                    )

                # Handle piece larger than chunk_size
                if len(piece) > self.chunk_size and remaining_separators:
                    sub_chunks = self._split_text(piece, remaining_separators)
                    for sub in sub_chunks:
                        sub["char_start"] += current_start + len(current_chunk)
                        sub["char_end"] += current_start + len(current_chunk)
                    chunks.extend(sub_chunks)
                    current_start += len(current_chunk) + len(piece)
                    current_chunk = ""
                else:
                    # Start new chunk with overlap
                    overlap_text = (
                        current_chunk[-self.chunk_overlap :]
                        if len(current_chunk) > self.chunk_overlap
                        else current_chunk
                    )
                    current_start += len(current_chunk) - len(overlap_text)
                    current_chunk = overlap_text + piece

        if current_chunk.strip():
            chunks.append(
                {
                    "content": current_chunk.strip(),
                    "char_start": current_start,
                    "char_end": current_start + len(current_chunk),
                }
            )

        return chunks


class SemanticChunker(ChunkingStrategy):
    """Semantic chunking based on embedding similarity."""

    def __init__(
        self,
        chunk_size: int = 1000,
        similarity_threshold: float = 0.5,
    ) -> None:
        """Initialize semantic chunker.

        Args:
            chunk_size: Maximum chunk size
            similarity_threshold: Threshold for combining sentences
        """
        self.chunk_size = chunk_size
        self.similarity_threshold = similarity_threshold

    def chunk(self, text: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Split text based on semantic similarity."""
        # Split into sentences
        sentences = self._split_sentences(text)

        if not sentences:
            return []

        # For now, fall back to simple sentence grouping
        # Full semantic chunking would require embedding each sentence
        chunks: list[dict[str, Any]] = []
        current_chunk = ""
        current_start = 0

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(
                        {
                            "content": current_chunk.strip(),
                            "char_start": current_start,
                            "char_end": current_start + len(current_chunk),
                        }
                    )
                current_start += len(current_chunk)
                current_chunk = sentence

        if current_chunk.strip():
            chunks.append(
                {
                    "content": current_chunk.strip(),
                    "char_start": current_start,
                    "char_end": current_start + len(current_chunk),
                }
            )

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        import re

        # Simple sentence splitting
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() + " " for s in sentences if s.strip()]


class DocumentStructureChunker(ChunkingStrategy):
    """Chunking based on document structure (headers, sections)."""

    def __init__(
        self,
        chunk_size: int = 2000,
        respect_headers: bool = True,
    ) -> None:
        """Initialize structure-aware chunker.

        Args:
            chunk_size: Maximum chunk size
            respect_headers: Keep headers with their content
        """
        self.chunk_size = chunk_size
        self.respect_headers = respect_headers

    def chunk(self, text: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Split text respecting document structure."""
        import re

        chunks: list[dict[str, Any]] = []

        # Find section headers (numbered or markdown-style)
        header_pattern = r"^(?:#{1,3}\s+|\d+\.\s+|[A-Z][A-Z\s]+:)(.+)$"

        sections: list[tuple[str, str, int]] = []  # (header, content, start_pos)
        current_header = ""
        current_content = ""
        current_start = 0

        for line in text.split("\n"):
            match = re.match(header_pattern, line, re.MULTILINE)

            if match:
                # Save previous section
                if current_content.strip():
                    sections.append((current_header, current_content, current_start))

                current_header = line
                current_content = ""
                current_start = text.find(line, current_start)
            else:
                current_content += line + "\n"

        # Add final section
        if current_content.strip():
            sections.append((current_header, current_content, current_start))

        # Convert sections to chunks
        for header, content, start_pos in sections:
            full_text = f"{header}\n{content}" if header else content

            if len(full_text) <= self.chunk_size:
                chunks.append(
                    {
                        "content": full_text.strip(),
                        "char_start": start_pos,
                        "char_end": start_pos + len(full_text),
                        "header": header.strip() if header else None,
                    }
                )
            else:
                # Split large sections
                sub_chunker = RecursiveCharacterChunker(chunk_size=self.chunk_size)
                sub_chunks = sub_chunker.chunk(full_text)

                for sub in sub_chunks:
                    sub["char_start"] += start_pos
                    sub["char_end"] += start_pos
                    sub["header"] = header.strip() if header else None
                    chunks.append(sub)

        return chunks


def get_chunker(
    strategy: str = "recursive",
    **kwargs: Any,
) -> ChunkingStrategy:
    """Get a chunker by strategy name.

    Args:
        strategy: "recursive", "semantic", or "structure"

    Returns:
        Chunking strategy instance
    """
    strategies = {
        "recursive": RecursiveCharacterChunker,
        "semantic": SemanticChunker,
        "structure": DocumentStructureChunker,
    }

    if strategy not in strategies:
        raise ValueError(f"Unknown strategy: {strategy}")

    return strategies[strategy](**kwargs)
