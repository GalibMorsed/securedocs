from dataclasses import dataclass
from app.rag.token_count import count_tokens

from app.services.document_extraction import ExtractedPage, normalize_text

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 200


@dataclass(frozen=True)
class ChunkData:
    chunk_index: int
    content: str
    page_number: int | None
    char_start: int
    char_end: int
    token_count: int


def chunk_pages(
    pages: list[ExtractedPage],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[ChunkData]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    chunks: list[ChunkData] = []
    absolute_offset = 0
    for page in pages:
        text = normalize_text(page.text)
        if text:
            start = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                if end < len(text):
                    end = _natural_boundary(text, start, end, chunk_size)
                raw = text[start:end]
                content = raw.strip()
                if content:
                    leading = len(raw) - len(raw.lstrip())
                    char_start = absolute_offset + start + leading
                    chunks.append(
                        ChunkData(
                            chunk_index=len(chunks),
                            content=content,
                            page_number=page.page_number,
                            char_start=char_start,
                            char_end=char_start + len(content),
                            token_count=count_tokens(content),
                        )
                    )
                if end >= len(text):
                    break
                start = max(start + 1, end - overlap)
                while start < len(text) and text[start].isspace():
                    start += 1
        absolute_offset += len(text) + 2
    return chunks


def _natural_boundary(text: str, start: int, end: int, chunk_size: int) -> int:
    search_start = start + max(1, int(chunk_size * 0.65))
    candidates = [
        text.rfind(separator, search_start, end)
        for separator in ("\n", ". ", " ", "\t")
    ]
    boundary = max(candidates)
    if boundary < search_start:
        return end
    # Keep sentence punctuation in this chunk; whitespace remains outside the slice.
    if text.startswith(". ", boundary):
        return boundary + 1
    return boundary
