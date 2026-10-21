"""Provider-neutral email models, contracts, and exceptions."""

from pintos_utils.email.contracts import EmailSender
from pintos_utils.email.exceptions import (
    EmailAuthenticationError,
    EmailConfigurationError,
    EmailError,
    EmailProviderError,
    EmailValidationError,
)
from pintos_utils.email.models import (
    EmailAddress,
    EmailAttachment,
    EmailMessage,
    SendResult,
)

__all__ = [
    "EmailAddress",
    "EmailAttachment",
    "EmailAuthenticationError",
    "EmailConfigurationError",
    "EmailError",
    "EmailMessage",
    "EmailProviderError",
    "EmailSender",
    "EmailValidationError",
    "SendResult",
]
