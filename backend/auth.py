"""Simple password hashing without bcrypt - uses SHA256 + salt"""
import hashlib, secrets, os

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}${h}"

def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, h = hashed.split("$", 1)
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == h
    except:
        return False


FULL_ACCESS_ROLES = frozenset({"ceo", "coo", "bd"})


def has_full_access(role: str | None) -> bool:
    """Vollzugriff: Ali (ceo), Sereina (coo) und Martino (bd)."""
    return role in FULL_ACCESS_ROLES
