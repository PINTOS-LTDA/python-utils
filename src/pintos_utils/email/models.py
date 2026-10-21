"""Immutable provider-neutral email models."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypeVar

from pintos_utils.email.exceptions import EmailValidationError

_T = TypeVar("_T")
_MEDIA_TYPE_PATTERN = re.compile(
    r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+/[!#$%&'*+\-.^_`|~0-9A-Za-z]+$"
)


def _reject_line_breaks(value: str, field_name: str) -> None:
    if "\r" in value or "\n" in value:
        raise EmailValidationError(f"{field_name} must not contain line breaks")


def _immutable_tuple(values: tuple[_T, ...], field_name: str) -> tuple[_T, ...]:
    try:
        return tuple(values)
    except TypeError as error:
        raise EmailValidationError(f"{field_name} must be an iterable") from error


@dataclass(frozen=True, slots=True)
class EmailAddress:
    """One email address with an optional display name."""

    address: str
    display_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.address, str) or not self.address.strip():
            raise EmailValidationError("address must be a non-empty string")
        _reject_line_breaks(self.address, "address")
        if self.display_name is not None:
            if not isinstance(self.display_name, str):
                raise EmailValidationError("display_name must be a string or None")
            _reject_line_breaks(self.display_name, "display_name")


@dataclass(frozen=True, slots=True)
class EmailAttachment:
    """An attachment whose bytes have already been read by the caller."""

    filename: str
    content: bytes
    content_type: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.filename, str) or not self.filename.strip():
            raise EmailValidationError("filename must be a non-empty string")
        _reject_line_breaks(self.filename, "filename")
        if not isinstance(self.content, bytes):
            raise EmailValidationError("content must be bytes")
        if self.content_type is not None:
            if not isinstance(
                self.content_type, str
            ) or not _MEDIA_TYPE_PATTERN.fullmatch(self.content_type):
                raise EmailValidationError("content_type must be a valid MIME type")


@dataclass(frozen=True, slots=True)
class EmailMessage:
    """Immutable message input shared by all provider implementations."""

    sender: EmailAddress
    subject: str
    to: tuple[EmailAddress, ...] = ()
    cc: tuple[EmailAddress, ...] = ()
    bcc: tuple[EmailAddress, ...] = ()
    text_body: str | None = None
    html_body: str | None = None
    attachments: tuple[EmailAttachment, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.sender, EmailAddress):
            raise EmailValidationError("sender must be an EmailAddress")
        if not isinstance(self.subject, str):
            raise EmailValidationError("subject must be a string")
        _reject_line_breaks(self.subject, "subject")

        for field_name in ("to", "cc", "bcc", "attachments"):
            values = _immutable_tuple(getattr(self, field_name), field_name)
            object.__setattr__(self, field_name, values)

        recipients = (*self.to, *self.cc, *self.bcc)
        if not recipients:
            raise EmailValidationError("message must have at least one recipient")
        if any(not isinstance(recipient, EmailAddress) for recipient in recipients):
            raise EmailValidationError("recipients must be EmailAddress instances")
        if any(not isinstance(item, EmailAttachment) for item in self.attachments):
            raise EmailValidationError("attachments must be EmailAttachment instances")
        if self.text_body is None and self.html_body is None:
            raise EmailValidationError("message must have a text_body or html_body")
        if self.text_body is not None and not isinstance(self.text_body, str):
            raise EmailValidationError("text_body must be a string or None")
        if self.html_body is not None and not isinstance(self.html_body, str):
            raise EmailValidationError("html_body must be a string or None")


@dataclass(frozen=True, slots=True)
class SendResult:
    """Provider acceptance result; it does not imply recipient delivery."""

    provider: str
    provider_message_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise EmailValidationError("provider must be a non-empty string")
        if self.provider_message_id is not None and not isinstance(
            self.provider_message_id, str
        ):
            raise EmailValidationError("provider_message_id must be a string or None")
