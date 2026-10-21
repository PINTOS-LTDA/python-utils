"""Provider-neutral email service contracts."""

from typing import Protocol

from pintos_utils.email.models import EmailMessage, SendResult


class EmailSender(Protocol):
    """Structural contract implemented by each email provider adapter."""

    def send(self, message: EmailMessage, /) -> SendResult:
        """Submit one message and return the provider acceptance result."""


__all__ = ["EmailSender"]
