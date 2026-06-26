from fittrack_mcp.auth import (
    AuthenticationError,
    authenticate_token,
    fingerprint_token,
)


def test_fingerprint_token_is_sha256_hex():
    assert (
        fingerprint_token("fittrack_phase0_dev_token")
        == "8d7290a9091a2b494e899f7e3ae5281a75eb243b05dcb619917049ad82fe2345"
    )


def test_authenticate_known_token():
    user = authenticate_token("fittrack_phase0_dev_token")

    assert user.user_id == "phase0-demo-user"


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
