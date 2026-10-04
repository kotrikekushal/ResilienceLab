from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest

from backend.config import settings
from backend.security.jwt import (
    create_access_token,
    decode_access_token,
)


def test_create_access_token():
    user_id = uuid4()

    token = create_access_token(user_id)

    assert isinstance(token, str)
    assert token


def test_decode_valid_access_token():
    user_id = uuid4()

    token = create_access_token(user_id)

    decoded_user_id = decode_access_token(token)

    assert decoded_user_id == user_id


def test_token_contains_user_id_and_expiration():
    user_id = uuid4()

    token = create_access_token(user_id)

    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )

    assert payload["sub"] == str(user_id)
    assert "exp" in payload


def test_invalid_token_is_rejected():
    invalid_token = "invalid.jwt.token"

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(invalid_token)


def test_expired_token_is_rejected():
    user_id = uuid4()

    expired_time = datetime.now(timezone.utc) - timedelta(
        minutes=1
    )

    payload = {
        "sub": str(user_id),
        "exp": expired_time,
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_token_with_wrong_signature_is_rejected():
    user_id = uuid4()

    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(
            minutes=30
        ),
    }

    token = jwt.encode(
        payload,
        "wrong-secret",
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


def test_token_without_subject_is_rejected():
    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(
            minutes=30
        ),
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(ValueError, match="Token subject is missing"):
        decode_access_token(token)