import hashlib

from fittrack_mcp.auth import (
    AuthenticationError,
    authenticate_authorization_header,
    authenticate_token,
    fingerprint_token,
)


TEST_TOKEN = "unit-test-token"


def test_fingerprint_token_is_sha256_hex():
    assert fingerprint_token(TEST_TOKEN) == hashlib.sha256(TEST_TOKEN.encode("utf-8")).hexdigest()


def test_authenticate_known_token(monkeypatch):
    monkeypatch.setattr(
        "fittrack_mcp.auth.KNOWN_TOKEN_FINGERPRINT",
        fingerprint_token(TEST_TOKEN),
    )

    user = authenticate_token(TEST_TOKEN)

    assert user.user_id == "phase0-demo-user"


def test_authenticate_authorization_header_strips_bearer_prefix(monkeypatch):
    monkeypatch.setattr(
        "fittrack_mcp.auth.KNOWN_TOKEN_FINGERPRINT",
        fingerprint_token(TEST_TOKEN),
    )

    user = authenticate_authorization_header(f"Bearer {TEST_TOKEN}")

    assert user.user_id == "phase0-demo-user"


def test_authenticate_authorization_header_requires_bearer_prefix():
    try:
        authenticate_authorization_header(TEST_TOKEN)
    except AuthenticationError as exc:
        assert str(exc) == "authentication failed"
    else:
        raise AssertionError("Expected AuthenticationError")


def test_authenticate_rejects_missing_token():
    try:
        authenticate_token(None)
    except AuthenticationError as exc:
        assert str(exc) == "authentication failed"
    else:
        raise AssertionError("Expected AuthenticationError")


def test_authenticate_rejects_wrong_token():
    try:
        authenticate_token("wrong-token")
    except AuthenticationError as exc:
        assert str(exc) == "authentication failed"
    else:
        raise AssertionError("Expected AuthenticationError")
