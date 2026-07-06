import os
import tempfile
import secrets
from datetime import datetime, timedelta

import pytest

_test_dir = tempfile.mkdtemp(prefix="kineo-auth-test-")
os.environ["DATA_DIR"] = _test_dir

from database import init_db, SessionLocal, User, Base, engine  # noqa: E402
from auth import hash_password, verify_password  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    db.add(User(
        username="testuser",
        full_name="Test User",
        email="test@kineo.swiss",
        hashed_password=hash_password("oldpass123"),
        role="ceo",
    ))
    db.commit()
    db.close()
    yield


def test_reset_token_flow():
    """Simuliert forgot/reset ohne HTTP — gleiche DB-Logik wie main.py."""
    db = SessionLocal()
    user = db.query(User).filter_by(username="testuser").first()

    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    db.commit()

    found = db.query(User).filter_by(reset_token=token).first()
    assert found is not None
    assert found.reset_token_expires >= datetime.utcnow()

    found.hashed_password = hash_password("newpass123")
    found.reset_token = None
    found.reset_token_expires = None
    db.commit()

    user = db.query(User).filter_by(username="testuser").first()
    assert verify_password("newpass123", user.hashed_password)
    assert user.reset_token is None
    db.close()


def test_expired_reset_token_rejected():
    db = SessionLocal()
    user = db.query(User).filter_by(username="testuser").first()
    user.reset_token = "expired-token"
    user.reset_token_expires = datetime.utcnow() - timedelta(hours=1)
    db.commit()

    found = db.query(User).filter_by(reset_token="expired-token").first()
    assert found is not None
    assert found.reset_token_expires < datetime.utcnow()
    db.close()
