"""Unit tests for auth utility functions."""
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from jose import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_HOURS,
)
from config import settings


class TestPasswordHashing:
    def test_hash_returns_string(self):
        hashed = hash_password("testpass")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_is_not_plaintext(self):
        hashed = hash_password("testpass")
        assert hashed != "testpass"

    def test_verify_correct_password(self):
        hashed = hash_password("mysecret")
        assert verify_password("mysecret", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("mysecret")
        assert verify_password("wrongpass", hashed) is False

    def test_different_passwords_produce_different_hashes(self):
        hash1 = hash_password("password1")
        hash2 = hash_password("password2")
        assert hash1 != hash2

    def test_same_password_produces_different_hashes(self):
        """bcrypt uses random salt, so same password -> different hash each time."""
        hash1 = hash_password("samepass")
        hash2 = hash_password("samepass")
        assert hash1 != hash2
        # But both should verify
        assert verify_password("samepass", hash1) is True
        assert verify_password("samepass", hash2) is True


class TestAccessToken:
    def test_create_token_returns_string(self):
        token = create_access_token({"sub": "testuser"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_subject(self):
        token = create_access_token({"sub": "testuser"})
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"

    def test_token_has_expiration(self):
        token = create_access_token({"sub": "testuser"})
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload
        exp = datetime.utcfromtimestamp(payload["exp"])
        assert exp > datetime.utcnow()

    def test_token_preserves_extra_data(self):
        token = create_access_token({"sub": "testuser", "role": "admin"})
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["role"] == "admin"

    def test_token_with_wrong_key_fails(self):
        token = create_access_token({"sub": "testuser"})
        with pytest.raises(Exception):
            jwt.decode(token, "wrong-secret-key", algorithms=[ALGORITHM])
