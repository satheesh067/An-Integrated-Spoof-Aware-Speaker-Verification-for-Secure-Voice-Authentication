"""Canonical speaker identifiers and safe upload suffixes for filesystem use."""
import re
from pathlib import Path


def canonical_username(value: str) -> str:
    username = value.strip().lower().replace(" ", "_")
    if not re.fullmatch(r"[a-z0-9_-]{1,64}", username):
        raise ValueError("Speaker ID must contain 1–64 letters, numbers, underscores or hyphens.")
    if username.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise ValueError("This speaker ID is reserved by the operating system.")
    return username


def audio_suffix(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".webm", ".aiff", ".aac"}:
        raise ValueError("Unsupported audio file extension.")
    return suffix
