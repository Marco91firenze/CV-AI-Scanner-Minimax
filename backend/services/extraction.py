"""Extract plain text from PDF and DOCX bytes."""

from __future__ import annotations

import io
from typing import Final

import fitz
from docx import Document

_MAX_CHARS: Final[int] = 120_000


def extract_text_from_bytes(data: bytes, filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _from_pdf(data)
    if lower.endswith(".docx"):
        return _from_docx(data)
    raise ValueError("Unsupported file type. Use PDF or DOCX.")


def _from_pdf(data: bytes) -> str:
    text_parts: list[str] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text() or "")
    text = "\n".join(text_parts).strip()
    return text[:_MAX_CHARS]


def _from_docx(data: bytes) -> str:
    bio = io.BytesIO(data)
    document = Document(bio)
    paras = [p.text for p in document.paragraphs if p.text]
    text = "\n".join(paras).strip()
    return text[:_MAX_CHARS]
