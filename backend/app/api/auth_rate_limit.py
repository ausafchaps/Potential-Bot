from ipaddress import ip_address

from fastapi import HTTPException, Request

from app.api.dependencies import Database
from app.core.config import settings
from app.services.auth_rate_limit import (
    AttemptLimit,
    AuthRateLimited,
    AuthRateLimitUnavailable,
    consume_attempts,
)


def client_identity(request: Request) -> str:
    if settings.auth_client_ip_source == "vercel":
        # Trust only Vercel's overwritten header, when enabled by deployment
        # configuration. A caller's Vercel-looking headers never enable trust.
        address = request.headers.get("x-vercel-forwarded-for", "")
        try:
            parsed = ip_address(address)
        except ValueError as exc:
            raise unavailable() from exc
    else:
        address = request.client.host if request.client else "unknown"
        try:
            parsed = ip_address(address)
        except ValueError:
            return address
    return str(getattr(parsed, "ipv4_mapped", None) or parsed)


def unavailable() -> HTTPException:
    return HTTPException(
        503,
        "Sign in and signup are temporarily unavailable. Please try again shortly.",
        headers={"Retry-After": "30", "Cache-Control": "no-store"},
    )


def enforce(db: Database, policies: list[AttemptLimit]) -> None:
    try:
        consume_attempts(db, policies)
    except AuthRateLimited as exc:
        raise HTTPException(
            429,
            f"Too many authentication attempts. Try again in {exc.retry_after} seconds.",
            headers={"Retry-After": str(exc.retry_after), "Cache-Control": "no-store"},
        ) from exc
    except AuthRateLimitUnavailable as exc:
        raise unavailable() from exc


def limit_signup(request: Request, db: Database) -> None:
    enforce(db, [AttemptLimit(
        "signup-ip", client_identity(request),
        settings.auth_signup_ip_limit, settings.auth_signup_window_seconds,
    )])


def limit_login_ip(request: Request, db: Database) -> None:
    enforce(db, [AttemptLimit(
        "login-ip", client_identity(request),
        settings.auth_login_ip_limit, settings.auth_login_window_seconds,
    )])


def limit_login_email(db: Database, email: str) -> None:
    enforce(db, [AttemptLimit(
        "login-email", email.strip().lower(),
        settings.auth_login_email_limit, settings.auth_login_window_seconds,
    )])
