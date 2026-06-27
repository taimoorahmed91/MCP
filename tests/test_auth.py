import hashlib

from fittrack_mcp.auth import (
    AuthenticationError,
    extract_bearer_token,
    fingerprint_token,
)


TEST_TOKEN = "unit-test-token"


def test_fingerprint_token_is_sha256_hex():
    assert fingerprint_token(TEST_TOKEN) == hashlib.sha256(TEST_TOKEN.encode("utf-8")).hexdigest()


def test_extract_bearer_token_strips_bearer_prefix():
    assert extract_bearer_token(f"Bearer {TEST_TOKEN}") == TEST_TOKEN


def test_extract_bearer_token_requires_bearer_prefix():
    try:
        extract_bearer_token(TEST_TOKEN)
    except AuthenticationError as exc:
        assert str(exc) == "authentication failed"
    else:
        raise AssertionError("Expected AuthenticationError")


def test_extract_bearer_token_rejects_missing_header():
    try:
        extract_bearer_token(None)
    except AuthenticationError as exc:
        assert str(exc) == "authentication failed"
    else:
        raise AssertionError("Expected AuthenticationError")


def test_extract_bearer_token_rejects_empty_token():
    try:
        extract_bearer_token("Bearer ")
    except AuthenticationError as exc:
        assert str(exc) == "authentication failed"
    else:
        raise AssertionError("Expected AuthenticationError")
