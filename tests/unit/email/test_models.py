from dataclasses import FrozenInstanceError

import pytest

from pintos_utils.email.exceptions import EmailValidationError
from pintos_utils.email.models import EmailAddress, EmailAttachment, EmailMessage


def make_sender() -> EmailAddress:
    return EmailAddress("sender@example.com")


@pytest.mark.parametrize("address", ["", " \t", "user@example.com\r\nBcc: x"])
def test_email_address_rejects_empty_or_unsafe_address(address: str) -> None:
    with pytest.raises(EmailValidationError):
        EmailAddress(address)


def test_email_address_rejects_line_break_in_display_name() -> None:
    with pytest.raises(EmailValidationError):
        EmailAddress("user@example.com", "User\nBcc: x")


def test_email_attachment_accepts_bytes_and_optional_media_type() -> None:
    attachment = EmailAttachment("report.csv", b"a,b\n1,2", "text/csv")
    binary_attachment = EmailAttachment("archive.bin", b"\x00\x01")

    assert attachment.content == b"a,b\n1,2"
    assert binary_attachment.content_type is None


@pytest.mark.parametrize("filename", ["", "  ", "report\r\n.txt"])
def test_email_attachment_rejects_empty_or_unsafe_filename(filename: str) -> None:
    with pytest.raises(EmailValidationError):
        EmailAttachment(filename, b"content")


@pytest.mark.parametrize("content_type", ["text", "text/plain\r\nBcc: x", "/plain"])
def test_email_attachment_rejects_invalid_media_type(content_type: str) -> None:
    with pytest.raises(EmailValidationError):
        EmailAttachment("file.txt", b"content", content_type)


def test_email_message_requires_a_recipient() -> None:
    with pytest.raises(EmailValidationError, match="recipient"):
        EmailMessage(sender=make_sender(), subject="Report", text_body="Hello")


def test_email_message_requires_at_least_one_body() -> None:
    with pytest.raises(EmailValidationError, match="body"):
        EmailMessage(
            sender=make_sender(),
            subject="Report",
            to=(EmailAddress("recipient@example.com"),),
        )


def test_email_message_supports_either_or_both_body_formats() -> None:
    recipient = EmailAddress("recipient@example.com")

    text_only = EmailMessage(
        sender=make_sender(), subject="Text", to=(recipient,), text_body="Hello"
    )
    html_only = EmailMessage(
        sender=make_sender(), subject="HTML", to=(recipient,), html_body="<p>Hello</p>"
    )
    both = EmailMessage(
        sender=make_sender(),
        subject="Both",
        to=(recipient,),
        text_body="Hello",
        html_body="<p>Hello</p>",
    )

    assert text_only.text_body == "Hello"
    assert html_only.html_body == "<p>Hello</p>"
    assert both.text_body == "Hello"
    assert both.html_body == "<p>Hello</p>"


def test_email_message_keeps_all_recipient_kinds_and_attachments_immutable() -> None:
    to = [EmailAddress("to@example.com")]
    cc = [EmailAddress("cc@example.com")]
    bcc = [EmailAddress("bcc@example.com")]
    attachments = [EmailAttachment("report.txt", b"report")]

    message = EmailMessage(
        sender=make_sender(),
        subject="Report",
        to=to,
        cc=cc,
        bcc=bcc,
        text_body="Attached.",
        attachments=attachments,
    )
    to.clear()
    cc.clear()
    bcc.clear()
    attachments.clear()

    assert len(message.to) == 1
    assert len(message.cc) == 1
    assert len(message.bcc) == 1
    assert len(message.attachments) == 1
    with pytest.raises(FrozenInstanceError):
        message.subject = "Changed"  # type: ignore[misc]


@pytest.mark.parametrize("subject", ["Report\r\nBcc: x", "Report\nCc: x"])
def test_email_message_rejects_header_injection(subject: str) -> None:
    with pytest.raises(EmailValidationError):
        EmailMessage(
            sender=make_sender(),
            subject=subject,
            to=(EmailAddress("recipient@example.com"),),
            text_body="Hello",
        )
