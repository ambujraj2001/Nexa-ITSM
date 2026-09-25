from __future__ import annotations

import re


def chunk_text(text: str, *, max_chars: int = 900, overlap: int = 120) -> list[str]:
    """Split markdown-ish text into retrieval chunks on heading/paragraph boundaries.

    Headings are carried into the chunks that follow them so each chunk keeps
    its context ("## Renewing the certificate" + the steps under it).
    """
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    chunks: list[str] = []
    current = ""
    heading = ""
    for block in blocks:
        if block.startswith("#"):
            heading = block.splitlines()[0].lstrip("#").strip()
        candidate = f"{current}\n\n{block}".strip() if current else (f"{heading}\n{block}" if heading and not block.startswith("#") else block)
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(block) > max_chars:
            cut = block.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            chunks.append(block[:cut].strip())
            block = block[max(0, cut - overlap):].strip()
        tail = chunks[-1][-overlap:] if chunks and overlap else ""
        prefix = f"{heading}\n" if heading and not block.startswith("#") else ""
        current = f"{prefix}{tail} {block}".strip() if tail and not prefix else f"{prefix}{block}".strip()
    if current:
        chunks.append(current)
    return chunks


def truncate(text: str | None, limit: int) -> str:
    if not text:
        return ""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
