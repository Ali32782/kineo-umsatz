"""Tests always use SQLite — ignore production DATABASE_URL."""
import os

os.environ.pop("DATABASE_URL", None)
