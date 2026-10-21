"""Provider-neutral fakes shared by email contract tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from pintos_utils.email.models import EmailMessage, SendResult


@dataclass(slots=True)
class FakeEmailSender:
    """Simple sender used to prove consumers can substitute providers."""

    sent_messages: list[EmailMessage] = field(default_factory=list)

    def send(self, message: EmailMessage, /) -> SendResult:
        self.sent_messages.append(message)
        return SendResult(provider="fake", provider_message_id="fake-123")
