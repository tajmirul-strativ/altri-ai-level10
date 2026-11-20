"""Signed session cookie (design.md §5). The cookie holds the user id plus a signature;
the server never trusts a user id it didn't sign."""

from fastapi import Response
from itsdangerous import BadSignature, TimestampSigner

from app.config import get_settings

COOKIE = "l10_session"
MAX_AGE = 7 * 24 * 3600


def _signer() -> TimestampSigner:
    return TimestampSigner(get_settings().session_secret, salt="l10-session")


def set_session(response: Response, user_id: str) -> None:
    response.set_cookie(
        COOKIE,
        _signer().sign(user_id).decode(),
        max_age=MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=get_settings().cookie_secure,
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


def read_session(cookie: str | None) -> str | None:
    if not cookie:
        return None
    try:
        return _signer().unsign(cookie, max_age=MAX_AGE).decode()
    except BadSignature:
        return None
