"""Password hashing — bcrypt (neu) mit Legacy-SHA256-Support."""
from __future__ import annotations

import hashlib
import secrets

import bcrypt

FULL_ACCESS_ROLES = frozenset({"ceo", "coo", "bd"})


def has_full_access(role: str | None) -> bool:
    """Vollzugriff: Ali (ceo), Sereina (coo) und Martino (bd)."""
    return role in FULL_ACCESS_ROLES


def hash_password(password: str) -> str:
    """Neues Hash-Format: bcrypt."""
    pw = (password or "").encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=12)).decode("ascii")


def _verify_legacy_sha256(password: str, hashed: str) -> bool:
    try:
        salt, digest = hashed.split("$", 1)
        if len(salt) != 32:
            return False
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == digest
    except (ValueError, TypeError):
        return False


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed or not password:
        return False
    try:
        if hashed.startswith("$2a$") or hashed.startswith("$2b$") or hashed.startswith("$2y$"):
            return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("ascii"))
        return _verify_legacy_sha256(password, hashed)
    except (ValueError, TypeError):
        return False


def needs_rehash(hashed: str | None) -> bool:
    """True wenn noch Legacy-SHA256 — nach Login auf bcrypt umstellen."""
    if not hashed:
        return True
    return not (hashed.startswith("$2a$") or hashed.startswith("$2b$") or hashed.startswith("$2y$"))


def normalize_person_name(name: str | None) -> str:
    """Vergleichshilfe für Signatur-Namen (case/whitespace/Punkt)."""
    import re
    s = (name or "").strip().lower()
    s = s.replace(".", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def names_match_confirm(expected_raw: str | None, given_raw: str | None) -> bool:
    """MA-Bestätigungsname vs. Stammdaten — Vorname reicht wenn eindeutig genug."""
    e = normalize_person_name(expected_raw)
    g = normalize_person_name(given_raw)
    if not e or not g or len(g) < 2:
        return False
    if e == g or e in g or g in e:
        return True
    ew, gw = e.split(), g.split()
    return bool(ew and gw and ew[0] == gw[0] and len(ew[0]) >= 3)
