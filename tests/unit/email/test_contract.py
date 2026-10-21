"""Tests for provider substitution and the optional Gmail dependency boundary."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fakes import FakeEmailSender

from pintos_utils.email import (
    EmailAddress,
    EmailMessage,
    EmailSender,
    SendResult,
)


def send_report(sender: EmailSender, message: EmailMessage) -> SendResult:
    """Representative consumer function typed only against the shared port."""
    return sender.send(message)


def test_provider_neutral_contract_accepts_an_independent_sender() -> None:
    fake = FakeEmailSender()
    message = EmailMessage(
        sender=EmailAddress("sender@example.com"),
        to=(EmailAddress("recipient@example.com"),),
        subject="Report",
        text_body="Hello",
    )

    result = send_report(fake, message)

    assert result == SendResult(provider="fake", provider_message_id="fake-123")
    assert fake.sent_messages == [message]


def test_importing_shared_email_api_does_not_load_google_sdk() -> None:
    source = Path(__file__).resolve().parents[3] / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source)
    code = (
        "import sys; import pintos_utils.email; "
        "assert not any(name == 'google' or name.startswith('google.') "
        "or name == 'googleapiclient' or name.startswith('googleapiclient.') "
        "for name in sys.modules)"
    )

    subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
