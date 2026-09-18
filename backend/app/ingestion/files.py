from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status

from app.chunking.splitter import RawChunk, split_tabular_rows, split_text
from app.config import Settings

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx"}
ALLOWED_MIME = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/plain", "application/octet-stream"},
    ".csv": {"text/csv", "text/plain", "application/vnd.ms-excel", "application/octet-stream"},
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
        "application/octet-stream",
    },
}


def sanitize_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return base[:200] or "upload.bin"


def validate_upload(filename: str, content_type: str | None, size: int, settings: Settings) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size <= 0 or size > max_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file size")
    return ext


def storage_name(ext: str) -> str:
    return f"{uuid4().hex}{ext}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _looks_like_text(data: bytes) -> bool:
    sample = data[:8192]
    if b"\x00" in sample:
        return False
    return True


class MalwareScanner:
    """Rejects executable and mismatched magic bytes. Not a substitute for antivirus."""

    def scan(self, data: bytes, filename: str) -> None:
        if not data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file size")
        if data.startswith((b"MZ", b"\x7fELF", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa")):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")
        lowered = filename.lower()
        if any(lowered.endswith(ext) for ext in (".exe", ".dll", ".bat", ".cmd", ".ps1", ".sh")):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")
        ext = Path(filename).suffix.lower()
        if ext == ".pdf" and not data.startswith(b"%PDF"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")
        if ext in {".docx", ".xlsx"} and not data.startswith(b"PK"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")
        if ext in {".txt", ".md", ".csv"} and not _looks_like_text(data):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")



def extract_chunks(data: bytes, ext: str, settings: Settings) -> list[RawChunk]:
    if ext == ".pdf":
        return _extract_pdf(data, settings)
    if ext == ".docx":
        return _extract_docx(data, settings)
    if ext in {".txt", ".md"}:
        text = data.decode("utf-8", errors="replace")
        return split_text(text, settings.chunk_size, settings.chunk_overlap)
    if ext == ".csv":
        return _extract_csv(data)
    if ext == ".xlsx":
        return _extract_xlsx(data)
    raise HTTPException(status_code=400, detail="Unsupported file type")


def _extract_pdf(data: bytes, settings: Settings) -> list[RawChunk]:
    import fitz
    import re

    chunks: list[RawChunk] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page_index, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            # Clean up OCR artifacts where a currency block is parsed as 'I'
            text = re.sub(r'(?<![A-Za-z])I(\d{1,3}(?:,\d{2,3})*(?:\.\d+)?)', r'\1', text)
            
            page_chunks = split_text(
                text,
                settings.chunk_size,
                settings.chunk_overlap,
                page_number=page_index,
            )
            for item in page_chunks:
                item.chunk_index = len(chunks)
                chunks.append(item)
    return chunks


def _extract_docx(data: bytes, settings: Settings) -> list[RawChunk]:
    from docx import Document as DocxDocument

    document = DocxDocument(io.BytesIO(data))
    parts: list[str] = []
    current_heading: str | None = None
    chunks: list[RawChunk] = []
    for para in document.paragraphs:
        style = (para.style.name if para.style else "") or ""
        text = para.text.strip()
        if not text:
            continue
        if style.startswith("Heading"):
            if parts:
                for item in split_text(
                    "\n".join(parts),
                    settings.chunk_size,
                    settings.chunk_overlap,
                    section_title=current_heading,
                ):
                    item.chunk_index = len(chunks)
                    chunks.append(item)
                parts = []
            current_heading = text
        parts.append(text)
    if parts:
        for item in split_text(
            "\n".join(parts), settings.chunk_size, settings.chunk_overlap, section_title=current_heading
        ):
            item.chunk_index = len(chunks)
            chunks.append(item)
    return chunks


def _extract_csv(data: bytes) -> list[RawChunk]:
    import pandas as pd

    frame = pd.read_csv(io.BytesIO(data), dtype=str).fillna("")
    headers = [str(c) for c in frame.columns.tolist()]
    rows = frame.astype(str).values.tolist()
    return split_tabular_rows(headers, rows, sheet_name="csv")


def _extract_xlsx(data: bytes) -> list[RawChunk]:
    import pandas as pd

    book = pd.read_excel(io.BytesIO(data), sheet_name=None, dtype=str)
    chunks: list[RawChunk] = []
    for sheet, frame in book.items():
        frame = frame.fillna("")
        headers = [str(c) for c in frame.columns.tolist()]
        rows = frame.astype(str).values.tolist()
        for item in split_tabular_rows(headers, rows, sheet_name=str(sheet)):
            item.chunk_index = len(chunks)
            chunks.append(item)
    return chunks
