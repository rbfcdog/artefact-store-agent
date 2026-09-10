
from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any

import pdfplumber

_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*?)$")
_PAGE_FOOTER = re.compile(r"^Página \d+$")
_HEADER_LINE = re.compile(r"^Empório da Música\s+Manual de Políticas", re.I)

_MAX_CHARS = 1200
_DOC_TAG = "Empório da Música - Manual de Políticas e Procedimentos v2.1"
_CHUNK_PREFIX = re.compile(r"^\[[^\]]*\]\n?")

def _looks_like_heading(number: str, title: str) -> bool:
    if len(title) > 90 or title.rstrip().endswith((".", ",", ";", ":")):
        return False
    return True

def normalize_text(text: str) -> str:
    lowered = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in lowered if not unicodedata.combining(c))

def extract_chunks(pdf_path: Path) -> list[tuple[str, str]]:
    with pdfplumber.open(pdf_path) as pdf:
        raw = "\n".join(page.extract_text() or "" for page in pdf.pages)

    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in raw.splitlines():
        line = line.strip()
        if not line or _PAGE_FOOTER.match(line) or _HEADER_LINE.match(line):
            continue
        m = _HEADING.match(line)
        if m and _looks_like_heading(m.group(1), m.group(2)):
            sections.append((f"{m.group(1)}. {m.group(2).strip()}", []))
        else:
            sections[-1][1].append(line)

    chunks: list[tuple[str, str]] = []
    for path, lines in sections:
        body = re.sub(r"\s+", " ", " ".join(lines)).strip()
        body = body.replace("\u2014", "-")
        if not body:
            continue
        for piece in _split_long(body, _MAX_CHARS):
            chunks.append((path or "Capa", f"[{_DOC_TAG} - {path or 'capa'}]\n{piece}"))
    return chunks

def _split_long(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[.;:])\s+", text)
    pieces, current = [], ""
    for s in sentences:
        if current and len(current) + len(s) + 1 > max_chars:
            pieces.append(current.strip())
            current = s
        else:
            current = f"{current} {s}".strip()
    if current.strip():
        pieces.append(current.strip())
    return pieces

def load_policy_chunks(con: sqlite3.Connection, pdf_path: Path) -> int:
    con.execute("DELETE FROM policy_chunks")
    for chunk_id, (section, text) in enumerate(extract_chunks(pdf_path), start=1):
        con.execute("INSERT INTO policy_chunks VALUES (?, ?, ?)", (chunk_id, section, text))
    con.commit()
    return con.execute("SELECT COUNT(*) FROM policy_chunks").fetchone()[0]

def _sections(con: sqlite3.Connection) -> list[tuple[str, str]]:
    joined: list[tuple[str, str]] = []
    for row in con.execute("SELECT section, text FROM policy_chunks ORDER BY chunk_id"):
        text = _CHUNK_PREFIX.sub("", row["text"])
        if joined and joined[-1][0] == row["section"]:
            joined[-1] = (joined[-1][0], f"{joined[-1][1]}\n{text}")
        else:
            joined.append((row["section"], text))
    return joined

def _section_number(title: str) -> str:
    m = re.match(r"^(\d+(?:\.\d+)*)", title)
    return m.group(1) if m else ""

def list_sections(con: sqlite3.Connection) -> list[str]:
    return [title for title, _ in _sections(con)]

def load_manual(con: sqlite3.Connection, section: str | None = None) -> dict[str, Any]:
    sections = _sections(con)
    if not section:
        return {"documento": _DOC_TAG,
                "secoes": [{"secao": s, "texto": t} for s, t in sections]}

    key = normalize_text(section.strip())
    if re.fullmatch(r"[\d.]+", key):
        picked = [(s, t) for s, t in sections
                  if _section_number(s) == key or _section_number(s).startswith(f"{key}.")]
    else:
        picked = [(s, t) for s, t in sections if key in normalize_text(f"{s} {t}")]

    if not picked:
        return {"documento": _DOC_TAG, "secoes": [],
                "secoes_disponiveis": [s for s, _ in sections]}
    return {"documento": _DOC_TAG,
            "secoes": [{"secao": s, "texto": t} for s, t in picked]}
