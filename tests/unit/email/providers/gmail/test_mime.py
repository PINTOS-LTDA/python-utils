"""Tests for Gmail MIME serialization."""

from __future__ import annotations

import base64
from email import policy
from email.parser import BytesParser

from pintos_utils.email.models import EmailAddress, EmailAttachment, EmailMessage
from pintos_utils.email.providers.gmail._mime import serialize_message


def test_serialization_preserves_to_cc_bcc_and_alternative_bodies() -> None:
    message = EmailMessage(
        sender=EmailAddress("sender@example.com", "Report Service"),
        to=(EmailAddress("to@example.com", "To Person"),),
        cc=(EmailAddress("cc@example.com"),),
        bcc=(EmailAddress("bcc@example.com"),),
        subject="Monthly report",
        text_body="The report is attached.",
        html_body="<p>The report is attached.</p>",
        attachments=(
            EmailAttachment("report.csv", b"month,total\nMay,12", "text/csv"),
            EmailAttachment("chart.bin", b"\x00\x01"),
        ),
    )

    raw = serialize_message(message)
    parsed = BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(raw)
    )

    assert parsed["From"].addresses[0].display_name == "Report Service"
    assert parsed["From"].addresses[0].addr_spec == "sender@example.com"
    assert "to@example.com" in parsed["To"]
    assert "cc@example.com" in parsed["Cc"]
    assert "bcc@example.com" in parsed["Bcc"]
    assert "bcc@example.com" not in parsed["To"]
    assert "bcc@example.com" not in parsed["Cc"]
    assert parsed.get_content_type() == "multipart/mixed"
    parts = list(parsed.iter_parts())
    assert parts[0].get_content_type() == "multipart/alternative"
    bodies = list(parts[0].iter_parts())
    assert bodies[0].get_content().replace("\r\n", "\n") == "The report is attached.\n"
    assert bodies[1].get_content().replace("\r\n", "\n") == (
        "<p>The report is attached.</p>\n"
    )
    assert [part.get_filename() for part in parts[1:]] == ["report.csv", "chart.bin"]


def test_serialization_supports_multiple_attachments() -> None:
    message = EmailMessage(
        sender=EmailAddress("sender@example.com"),
        to=(EmailAddress("to@example.com"),),
        subject="Files",
        text_body="See attached.",
        attachments=(
            EmailAttachment("first.txt", b"first", "text/plain"),
            EmailAttachment("second.bin", b"\x00\xff"),
        ),
    )

    raw = serialize_message(message)
    parsed = BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(raw)
    )
    attachments = [part for part in parsed.iter_attachments()]

    assert [part.get_filename() for part in attachments] == ["first.txt", "second.bin"]
    assert [part.get_payload(decode=True) for part in attachments] == [
        b"first",
        b"\x00\xff",
    ]
    assert attachments[0].get_content_type() == "text/plain"
    assert attachments[1].get_content_type() == "application/octet-stream"


def test_serialized_payload_is_urlsafe_base64_without_line_breaks() -> None:
    message = EmailMessage(
        sender=EmailAddress("sender@example.com"),
        to=(EmailAddress("to@example.com"),),
        subject="Payload",
        text_body="symbols: \xfb\xff",
    )

    raw = serialize_message(message)

    assert "\n" not in raw
    assert "+" not in raw
    assert "/" not in raw
    assert base64.urlsafe_b64decode(raw)
