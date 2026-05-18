"""Skip system-generated summaries, translations, and other non-source attachments."""

from __future__ import annotations

from pathlib import Path

_TRANSLATABLE_EXTENSIONS = frozenset({".pdf", ".txt", ".md", ".doc", ".docx"})

# Exact filenames produced by this assistant (or prior runs).
_SYSTEM_OUTPUT_NAMES = frozenset(
    {
        "summary.md",
        "translated.md",
        "translation.md",
    }
)

# Filename patterns for outputs we generate.
_OUTPUT_MARKERS = (
    ".translated.",
    ".translation.",
)


def is_translatable_source_attachment(path: str | Path) -> bool:
    """Return True only for user/source attachments that should be translated."""
    p = Path(path)
    name = p.name
    name_lower = name.lower()

    if name_lower in _SYSTEM_OUTPUT_NAMES:
        return False

    if name_lower.startswith("body_") and name_lower.endswith(".txt"):
        return False

    if name_lower.startswith(("translated-", "translated_")):
        return False

    if any(marker in name_lower for marker in _OUTPUT_MARKERS):
        return False

    if name_lower.endswith(".en.pdf") or ".en." in name_lower:
        return False

    # Paths under assistant output folders are never re-processed.
    parts_lower = {part.lower() for part in p.parts}
    if parts_lower & {"translations", "ai_inbox", "ai_agent"}:
        return False

    return p.suffix.lower() in _TRANSLATABLE_EXTENSIONS
