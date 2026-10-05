import base64
import hashlib
import hmac
import os
import re
import secrets
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from .config import settings

# scrypt parameters (OWASP: N=2^17, r=8, p=1). Stored with the hash so they can be raised later.
# SCRYPT_LOG_N exists only so the test suite can run fast; never lower it in production.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** int(os.environ.get("SCRYPT_LOG_N", "17")), 8, 1
SCRYPT_MAXMEM = 256 * 1024 * 1024


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, maxmem=SCRYPT_MAXMEM, dklen=32
    )
    b64 = base64.b64encode
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${b64(salt).decode()}${b64(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest_b64)
        digest = hashlib.scrypt(
            password.encode(),
            salt=base64.b64decode(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            maxmem=SCRYPT_MAXMEM,
            dklen=len(expected),
        )
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


# Equalizes login timing when the e-mail does not exist.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


def password_problem(password: str) -> str | None:
    if len(password) < 10:
        return "A senha precisa ter pelo menos 10 caracteres."
    if len(password) > 200:
        return "A senha é longa demais."
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "Use letras e números na senha."
    return None


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


class EncryptionNotConfigured(RuntimeError):
    pass


def cipher() -> MultiFernet:
    keys = settings.encryption_keys
    if not keys:
        raise EncryptionNotConfigured("TOKEN_ENCRYPTION_KEYS não configurada")
    return MultiFernet([Fernet(key.encode()) for key in keys])


def encrypt(value: str | None) -> str | None:
    return cipher().encrypt(value.encode()).decode() if value else None


def decrypt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return cipher().decrypt(value.encode()).decode()
    except InvalidToken as error:
        raise EncryptionNotConfigured("Não foi possível decifrar o token com as chaves atuais") from error


def rotate(value: str | None) -> str | None:
    """Re-encrypt with the newest key (MultiFernet.rotate)."""
    return cipher().rotate(value.encode()).decode() if value else None


SENSITIVE_KEYS = re.compile(r"token|secret|password|authorization|cookie|verifier|email|phone|gclid", re.IGNORECASE)
TOKENISH = re.compile(r"(ya29\.[\w\-.]+|1//[\w\-.]+|Bearer\s+[\w\-.]+)")


def redact(value: Any, depth: int = 0) -> Any:
    """Removes secrets and personal data before anything is logged or written to the audit trail."""
    if depth > 6:
        return "…"
    if isinstance(value, dict):
        return {k: ("[redacted]" if SENSITIVE_KEYS.search(str(k)) else redact(v, depth + 1)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact(v, depth + 1) for v in list(value)[:50]]
    if isinstance(value, str):
        return TOKENISH.sub("[redacted]", value)[:500]
    return value
