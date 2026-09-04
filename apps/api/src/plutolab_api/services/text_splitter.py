"""Recursive semantic text splitter for RAG chunking (Phase 4.2.b).

Features:
- Hierarchical recursive splitting with multi-language (Chinese + English) typography awareness.
- Sliding window token budgeting with configurable chunk_size (default 512) and overlap (default 64).
- Automatic provenance tracking (page_number, start_char, end_char, doc_char_offset) for Citations.
- Fast token counting via tiktoken (cl100k_base) with reliable heuristic offline fallback.
"""

from dataclasses import dataclass, field
from typing import Any

import structlog

from plutolab_api.services.doc_parser import ParsedDocument

logger = structlog.get_logger(__name__)

# Default separators ordered from largest semantic block to smallest unit
DEFAULT_SEPARATORS: list[str] = [
    "\n\n",  # Double newlines (paragraphs)
    "\n",  # Single newline (lines / headings)
    "。\n",  # Chinese sentence ending with newline
    "。",  # Chinese full stop
    "！",  # Chinese exclamation
    "？",  # Chinese question mark
    ". ",  # English period
    "! ",  # English exclamation
    "? ",  # English question mark
    "；",  # Chinese semicolon
    "; ",  # English semicolon
    " ",  # Word space
    "",  # Character level hard split fallback
]

# Initialize tiktoken cl100k_base encoder
try:
    import tiktoken

    _TIKTOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")
except Exception as exc:  # pragma: no cover
    logger.warning("tiktoken_init_fallback", error=str(exc))
    _TIKTOKEN_ENCODER = None


def count_tokens(text: str) -> int:
    """Calculate token count using tiktoken cl100k_base with heuristic fallback."""
    if not text:
        return 0

    if _TIKTOKEN_ENCODER is not None:
        try:
            return len(_TIKTOKEN_ENCODER.encode(text, disallowed_special=()))
        except Exception:  # pragma: no cover
            pass

    # Fast heuristic approximation: ~1.2 tokens per CJK char, ~0.28 per Latin char
    cjk_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    non_cjk = len(text) - cjk_count
    return max(1, int(cjk_count * 1.2 + non_cjk * 0.28))


@dataclass
class DocumentChunk:
    """A semantic text chunk with spatial/provenance metadata for vector indexing and citation."""

    chunk_index: int
    content: str
    token_count: int
    char_count: int
    page_number: int  # 1-indexed
    start_char: int  # Starting char position in page/section
    end_char: int  # Ending char position in page/section
    doc_char_offset: int  # Global char offset in full document
    metadata: dict[str, Any] = field(default_factory=dict)


class RecursiveSplitter:
    """Splits long text documents into overlapping semantic chunks with token budgeting."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        separators: list[str] | None = None,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap cannot be negative, got {chunk_overlap}")
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be strictly smaller than chunk_size ({chunk_size})"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or list(DEFAULT_SEPARATORS)

    def split_text(self, text: str) -> list[str]:
        """Split a raw text string into a list of chunk strings."""
        stripped = text.strip()
        if not stripped:
            return []

        if count_tokens(stripped) <= self.chunk_size:
            return [stripped]

        return self._split_text(stripped, self.separators)

    def split_document(self, parsed_doc: ParsedDocument) -> list[DocumentChunk]:
        """Split a `ParsedDocument` into indexed `DocumentChunk` items with page & offset metadata."""
        if not parsed_doc.text.strip():
            return []

        chunks: list[DocumentChunk] = []
        global_offset = 0
        chunk_idx = 0

        for page in parsed_doc.pages:
            page_text = page.text.strip()
            if not page_text:
                continue

            # Split the page text
            page_chunk_strings = self.split_text(page_text)
            search_cursor = 0

            for chunk_str in page_chunk_strings:
                # Find start position in page text
                found_idx = page_text.find(chunk_str, search_cursor)
                if found_idx == -1:
                    # If overlapping prefix was modified/trimmed, fallback to cursor
                    start_char = search_cursor
                else:
                    start_char = found_idx

                end_char = start_char + len(chunk_str)
                # Advance cursor with overlap consideration
                search_cursor = max(0, end_char - len(chunk_str) // 2)

                doc_char_offset = global_offset + start_char
                token_len = count_tokens(chunk_str)

                # Assemble metadata
                chunk_meta = dict(parsed_doc.metadata)
                chunk_meta.update(
                    {
                        "page_number": page.page_number,
                        "start_char": start_char,
                        "end_char": end_char,
                        "doc_char_offset": doc_char_offset,
                        "token_count": token_len,
                    }
                )

                chunk = DocumentChunk(
                    chunk_index=chunk_idx,
                    content=chunk_str,
                    token_count=token_len,
                    char_count=len(chunk_str),
                    page_number=page.page_number,
                    start_char=start_char,
                    end_char=end_char,
                    doc_char_offset=doc_char_offset,
                    metadata=chunk_meta,
                )
                chunks.append(chunk)
                chunk_idx += 1

            # Increment global char offset by page length + 2 (double newline separator between pages)
            global_offset += len(page_text) + 2

        return chunks

    def _split_text(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split text by cascading through separator hierarchy."""
        final_chunks: list[str] = []

        # Find the appropriate separator
        separator = ""
        new_separators: list[str] = []
        for i, s in enumerate(separators):
            if s == "":
                separator = ""
                break
            if s in text:
                separator = s
                new_separators = separators[i + 1 :]
                break

        # Split text by separator
        if separator:
            splits = text.split(separator)
        else:
            # Character by character hard split when no separator left
            splits = list(text)

        # Collect atomic pieces
        good_splits: list[str] = []
        for s in splits:
            if not s.strip() and separator != "":
                continue

            if count_tokens(s) < self.chunk_size:
                good_splits.append(s)
            else:
                if new_separators:
                    other_chunks = self._split_text(s, new_separators)
                    good_splits.extend(other_chunks)
                else:
                    # Slicing fallback by token size
                    good_splits.extend(self._slice_large_text(s))

        # Recombine atomic pieces into chunks respecting chunk_size & chunk_overlap
        if not good_splits:
            return []

        merged_chunks = self._merge_splits(good_splits, separator)
        for chunk in merged_chunks:
            if chunk.strip():
                final_chunks.append(chunk.strip())

        return final_chunks

    def _merge_splits(self, splits: list[str], separator: str) -> list[str]:
        """Greedily combine small text pieces into chunks with sliding overlap."""
        chunks: list[str] = []
        current_doc: list[str] = []
        total_tokens = 0

        sep_tokens = count_tokens(separator) if separator else 0

        for piece in splits:
            piece_tokens = count_tokens(piece)

            if total_tokens + piece_tokens + (sep_tokens if current_doc else 0) > self.chunk_size:
                if current_doc:
                    doc_str = separator.join(current_doc)
                    if doc_str.strip():
                        chunks.append(doc_str)

                    # Calculate overlap: keep pieces from tail of current_doc up to chunk_overlap
                    while total_tokens > self.chunk_overlap and current_doc:
                        removed = current_doc.pop(0)
                        total_tokens -= count_tokens(removed) + (sep_tokens if current_doc else 0)

                    total_tokens = max(0, total_tokens)

            current_doc.append(piece)
            total_tokens += piece_tokens + (sep_tokens if len(current_doc) > 1 else 0)

        if current_doc:
            doc_str = separator.join(current_doc)
            if doc_str.strip():
                chunks.append(doc_str)

        return chunks

    def _slice_large_text(self, text: str) -> list[str]:
        """Hard slice arbitrary long text without separators using a token binary search."""
        slices: list[str] = []
        remaining = text

        while remaining:
            if count_tokens(remaining) <= self.chunk_size:
                slices.append(remaining)
                break

            # Binary search character cut point that fits within chunk_size tokens
            low = 1
            high = len(remaining)
            best_idx = 1

            while low <= high:
                mid = (low + high) // 2
                prefix = remaining[:mid]
                if count_tokens(prefix) <= self.chunk_size:
                    best_idx = mid
                    low = mid + 1
                else:
                    high = mid - 1

            slices.append(remaining[:best_idx])
            # Step forward accounting for overlap characters
            step = max(1, best_idx - int(best_idx * (self.chunk_overlap / self.chunk_size)))
            remaining = remaining[step:]

        return slices
