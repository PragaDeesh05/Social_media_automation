import pytest
from app.core.security import encrypt_token, decrypt_token, redact_secret


def test_fernet_token_encryption_cycle():
    raw_token = "oauth2_token_xyz9876543210_secret_payload"
    encrypted = encrypt_token(raw_token)
    assert encrypted != raw_token
    assert len(encrypted) > 20

    decrypted = decrypt_token(encrypted)
    assert decrypted == raw_token


def test_secret_redaction():
    secret = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    redacted = redact_secret(secret)
    assert redacted.startswith("ghp_")
    assert redacted.endswith("wxyz")
    assert "..." in redacted
    assert "1234567890" not in redacted
