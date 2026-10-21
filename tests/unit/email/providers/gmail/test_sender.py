"""Network-free tests for the Gmail adapter."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from googleapiclient.errors import HttpError

from pintos_utils.email import (
    EmailAddress,
    EmailAuthenticationError,
    EmailMessage,
    EmailProviderError,
    SendResult,
)
from pintos_utils.email.providers.gmail import GMAIL_SEND_SCOPE, GmailEmailSender
from pintos_utils.email.providers.gmail import sender as gmail_sender


class FakeCredentials:
    def __init__(
        self,
        *,
        valid: bool = True,
        refresh_token: str | None = "refresh-token",
        refresh_error: Exception | None = None,
    ) -> None:
        self.valid = valid
        self.refresh_token = refresh_token
        self.refresh_error = refresh_error
        self.refresh_calls: list[object] = []

    def refresh(self, request: object) -> None:
        self.refresh_calls.append(request)
        if self.refresh_error is not None:
            raise self.refresh_error
        self.valid = True


class FakeMessages:
    def __init__(self, *, response: dict[str, Any] | None = None) -> None:
        self.response = response or {"id": "gmail-message-123"}
        self.request: dict[str, Any] | None = None
        self.error: Exception | None = None

    def send(self, **kwargs: Any) -> FakeMessages:
        self.request = kwargs
        return self

    def execute(self) -> dict[str, Any]:
        if self.error is not None:
            raise self.error
        return self.response


class FakeUsers:
    def __init__(self, messages: FakeMessages) -> None:
        self._messages = messages

    def messages(self) -> FakeMessages:
        return self._messages


class FakeService:
    def __init__(self, messages: FakeMessages) -> None:
        self._users = FakeUsers(messages)

    def users(self) -> FakeUsers:
        return self._users


def make_message() -> EmailMessage:
    return EmailMessage(
        sender=EmailAddress("sender@example.com"),
        to=(EmailAddress("recipient@example.com"),),
        subject="Test",
        text_body="Hello",
    )


def make_http_error(status: int, reason: str | None = None) -> HttpError:
    details = {"error": {"errors": [{"reason": reason}]}} if reason else {}
    return HttpError(
        SimpleNamespace(status=status, reason="test failure"),
        json.dumps(details).encode("utf-8"),
        uri="https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
    )


def test_sender_uses_send_scope_and_returns_structured_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = FakeMessages()
    credentials = FakeCredentials()
    monkeypatch.setattr(
        gmail_sender, "_build_service", lambda supplied: FakeService(messages)
    )

    result = GmailEmailSender(credentials).send(make_message())

    assert GMAIL_SEND_SCOPE == "https://www.googleapis.com/auth/gmail.send"
    assert isinstance(result, SendResult)
    assert result.provider == "gmail"
    assert result.provider_message_id == "gmail-message-123"
    assert messages.request is not None
    assert messages.request["userId"] == "me"
    assert "raw" in messages.request["body"]


def test_sender_allows_accepted_response_without_provider_message_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = FakeMessages(response={"threadId": "thread-only"})
    monkeypatch.setattr(
        gmail_sender, "_build_service", lambda supplied: FakeService(messages)
    )

    result = GmailEmailSender(FakeCredentials()).send(make_message())

    assert result == SendResult(provider="gmail", provider_message_id=None)


def test_sender_refreshes_invalid_credentials_before_building_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credentials = FakeCredentials(valid=False)
    messages = FakeMessages()
    build_states: list[bool] = []

    def build(supplied: FakeCredentials) -> FakeService:
        build_states.append(supplied.valid)
        return FakeService(messages)

    monkeypatch.setattr(gmail_sender, "_build_service", build)
    monkeypatch.setattr(gmail_sender, "_refresh_request", object)

    GmailEmailSender(credentials).send(make_message())

    assert len(credentials.refresh_calls) == 1
    assert build_states == [True]


def test_refresh_failure_is_chained_as_authentication_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = RuntimeError("private refresh response")
    credentials = FakeCredentials(valid=False, refresh_error=failure)
    monkeypatch.setattr(gmail_sender, "_refresh_request", object)

    with pytest.raises(EmailAuthenticationError) as raised:
        GmailEmailSender(credentials).send(make_message())

    assert raised.value.__cause__ is failure
    assert "private refresh response" not in str(raised.value)


@pytest.mark.parametrize(
    ("status", "reason", "retryable"),
    [
        (503, None, True),
        (503, "unknownReason", True),
        (429, None, True),
        (403, "rateLimitExceeded", True),
        (403, "userRateLimitExceeded", True),
        (403, "dailyLimitExceeded", False),
        (403, "domainPolicy", False),
        (403, "unknownReason", None),
        (403, None, None),
        (400, "badRequest", False),
        (404, "notFound", False),
        (418, "unknownReason", None),
    ],
)
def test_provider_http_failures_map_retryability(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    reason: str | None,
    retryable: bool | None,
) -> None:
    messages = FakeMessages()
    failure = make_http_error(status, reason)
    messages.error = failure
    monkeypatch.setattr(
        gmail_sender, "_build_service", lambda supplied: FakeService(messages)
    )

    with pytest.raises(EmailProviderError) as raised:
        GmailEmailSender(FakeCredentials()).send(make_message())

    assert raised.value.retryable is retryable
    assert raised.value.provider == "gmail"
    assert raised.value.__cause__ is failure
    assert "recipient@example.com" not in str(raised.value)


@pytest.mark.parametrize("reason", ["authError", "invalidCredentials"])
def test_authentication_http_failure_maps_to_authentication_error(
    monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    messages = FakeMessages()
    failure = make_http_error(401, reason)
    messages.error = failure
    monkeypatch.setattr(
        gmail_sender, "_build_service", lambda supplied: FakeService(messages)
    )

    with pytest.raises(EmailAuthenticationError) as raised:
        GmailEmailSender(FakeCredentials()).send(make_message())

    assert raised.value.__cause__ is failure


def test_timeout_without_http_response_has_unknown_retryability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = FakeMessages()
    failure = TimeoutError("private timeout details")
    messages.error = failure
    monkeypatch.setattr(
        gmail_sender, "_build_service", lambda supplied: FakeService(messages)
    )

    with pytest.raises(EmailProviderError) as raised:
        GmailEmailSender(FakeCredentials()).send(make_message())

    assert raised.value.retryable is None
    assert raised.value.__cause__ is failure
    assert "private timeout details" not in str(raised.value)


def test_missing_refresh_token_is_authentication_error() -> None:
    credentials = FakeCredentials(valid=False, refresh_token=None)

    with pytest.raises(EmailAuthenticationError):
        GmailEmailSender(credentials).send(make_message())
