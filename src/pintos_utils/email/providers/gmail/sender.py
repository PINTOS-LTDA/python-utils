"""Optional Gmail API implementation of the provider-neutral email contract."""

from __future__ import annotations

import json
from typing import Any, Protocol, cast

from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from pintos_utils.email.contracts import EmailSender
from pintos_utils.email.exceptions import (
    EmailAuthenticationError,
    EmailConfigurationError,
    EmailProviderError,
)
from pintos_utils.email.models import EmailMessage, SendResult
from pintos_utils.email.providers.gmail._mime import serialize_message

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
_PROVIDER = "gmail"
_TRANSIENT_STATUSES = {429, 500, 502, 503, 504}
_AUTH_REASONS = {"authError", "invalidCredentials", "insufficientPermissions"}
_PERMANENT_REASONS = {
    "badRequest",
    "invalidArgument",
    "invalidParameter",
    "notFound",
    "required",
    "requestTooLarge",
}


class _RefreshableCredentials(Protocol):
    @property
    def valid(self) -> bool: ...

    @property
    def refresh_token(self) -> str | None: ...

    def refresh(self, request: Request) -> None: ...


def _build_service(credentials: Credentials) -> Any:
    """Create the discovery client at the optional dependency boundary."""
    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )


def _refresh_request() -> Request:
    return Request()


def _error_reason(error: HttpError) -> str | None:
    try:
        payload = json.loads(error.content.decode("utf-8"))
        entries = payload.get("error", {}).get("errors", [])
        if entries and isinstance(entries[0], dict):
            reason = entries[0].get("reason")
            return reason if isinstance(reason, str) else None
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return None
    return None


def _http_status(error: HttpError) -> int | None:
    try:
        return int(error.resp.status)
    except (AttributeError, TypeError, ValueError):
        return None


def _retryability(status: int | None, reason: str | None) -> bool | None:
    if status in _TRANSIENT_STATUSES:
        return True
    if status == 403:
        if reason in {"rateLimitExceeded", "userRateLimitExceeded"}:
            return True
        if reason in {"dailyLimitExceeded", "domainPolicy"}:
            return False
        return None
    if reason in _PERMANENT_REASONS:
        return False
    return None


class GmailEmailSender(EmailSender):
    """Send provider-neutral messages through Gmail using consumer credentials."""

    def __init__(self, credentials: Credentials) -> None:
        if credentials is None:
            raise EmailConfigurationError("Gmail credentials are required")
        self._credentials = credentials

    def _refresh_credentials(self) -> None:
        credentials = cast(_RefreshableCredentials, self._credentials)
        if credentials.valid:
            return
        if not credentials.refresh_token:
            raise EmailAuthenticationError(
                "Gmail credentials are invalid and cannot be refreshed"
            )
        try:
            credentials.refresh(_refresh_request())
        except Exception as error:
            raise EmailAuthenticationError("Gmail credential refresh failed") from error
        if not credentials.valid:
            raise EmailAuthenticationError(
                "Gmail credentials remain invalid after refresh"
            )

    def send(self, message: EmailMessage, /) -> SendResult:
        """Submit one message and return Gmail's acceptance identifier."""
        self._refresh_credentials()
        try:
            service = _build_service(self._credentials)
            response = (
                service.users()
                .messages()
                .send(userId="me", body={"raw": serialize_message(message)})
                .execute()
            )
        except HttpError as error:
            status = _http_status(error)
            reason = _error_reason(error)
            if status == 401 or reason in _AUTH_REASONS:
                raise EmailAuthenticationError("Gmail authentication failed") from error
            raise EmailProviderError(
                "Gmail provider request failed",
                provider=_PROVIDER,
                retryable=_retryability(status, reason),
            ) from error
        except Exception as error:
            raise EmailProviderError(
                "Gmail provider request failed",
                provider=_PROVIDER,
                retryable=None,
            ) from error

        message_id = response.get("id") if isinstance(response, dict) else None
        return SendResult(
            provider=_PROVIDER,
            provider_message_id=message_id if isinstance(message_id, str) else None,
        )


__all__ = ["GMAIL_SEND_SCOPE", "GmailEmailSender"]
