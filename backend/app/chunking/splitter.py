from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class RawChunk:
    content: str
    chunk_index: int
    section_title: str | None = None
    page_number: int | None = None
    source_location: str | None = None


def _approx_tokens(text: str) -> int:
    return max(1, len(text.split()))


def split_text(
    text: str,
    chunk_size: int = 600,
    overlap: int = 80,
    page_number: int | None = None,
    section_title: str | None = None,
) -> list[RawChunk]:
    cleaned = re.sub(r"\r\n?", "\n", text).strip()
    if not cleaned:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", cleaned) if p.strip()]
    pieces: list[str] = []
    buf = ""
    for para in paragraphs:
        if _approx_tokens(para) > chunk_size:
            if buf:
                pieces.append(buf.strip())
                buf = ""
            words = para.split()
            step = max(1, chunk_size - overlap)
            for i in range(0, len(words), step):
                pieces.append(" ".join(words[i : i + chunk_size]))
            continue
        if _approx_tokens(buf) + _approx_tokens(para) <= chunk_size:
            buf = f"{buf}\n\n{para}".strip()
        else:
            if buf:
                pieces.append(buf)
            buf = para
    if buf:
        pieces.append(buf)

    overlapped: list[str] = []
    prev_tail = ""
    for piece in pieces:
        combined = f"{prev_tail} {piece}".strip() if prev_tail else piece
        overlapped.append(combined)
        words = combined.split()
        prev_tail = " ".join(words[-overlap:]) if overlap and len(words) > overlap else ""

    return [
        RawChunk(
            content=item,
            chunk_index=idx,
            section_title=section_title,
            page_number=page_number,
            source_location=f"chunk:{idx}",
        )
        for idx, item in enumerate(overlapped)
        if item.strip()
    ]


def split_tabular_rows(
    headers: list[str],
    rows: list[list[str]],
    sheet_name: str | None = None,
    max_rows_per_chunk: int = 8,
) -> list[RawChunk]:
    chunks: list[RawChunk] = []
    header_line = " | ".join(headers)
    for start in range(0, len(rows), max_rows_per_chunk):
        batch = rows[start : start + max_rows_per_chunk]
        lines = [header_line]
        for i, row in enumerate(batch):
            lines.append(" | ".join(row))
        content = "\n".join(lines)
        idx = len(chunks)
        location = f"{sheet_name or 'sheet'}:rows:{start + 1}-{start + len(batch)}"
        chunks.append(
            RawChunk(
                content=content,
                chunk_index=idx,
                section_title=sheet_name,
                source_location=location,
            )
        )
    return chunks
