"""Private MIME serialization for the Gmail adapter."""

from __future__ import annotations

import base64
from email import policy
from email.message import EmailMessage as MimeMessage
from email.utils import formataddr

from pintos_utils.email.models import EmailAddress, EmailMessage


def _format_address(value: EmailAddress) -> str:
    return formataddr((value.display_name or "", value.address))


def serialize_message(message: EmailMessage) -> str:
    """Return an RFC-compliant message encoded for Gmail's ``raw`` field."""
    mime = MimeMessage(policy=policy.SMTP)
    mime["From"] = _format_address(message.sender)
    if message.to:
        mime["To"] = ", ".join(_format_address(item) for item in message.to)
    if message.cc:
        mime["Cc"] = ", ".join(_format_address(item) for item in message.cc)
    if message.bcc:
        mime["Bcc"] = ", ".join(_format_address(item) for item in message.bcc)
    mime["Subject"] = message.subject

    if message.text_body is not None:
        mime.set_content(message.text_body)
        if message.html_body is not None:
            mime.add_alternative(message.html_body, subtype="html")
    else:
        mime.set_content(message.html_body or "", subtype="html")

    for attachment in message.attachments:
        content_type = attachment.content_type or "application/octet-stream"
        maintype, subtype = content_type.split("/", maxsplit=1)
        mime.add_attachment(
            attachment.content,
            maintype=maintype,
            subtype=subtype,
            filename=attachment.filename,
        )

    return base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
