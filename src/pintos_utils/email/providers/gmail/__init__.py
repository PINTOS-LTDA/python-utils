"""Optional Gmail email provider adapter."""

try:
    from pintos_utils.email.providers.gmail.sender import (
        GMAIL_SEND_SCOPE,
        GmailEmailSender,
    )
except ModuleNotFoundError as error:
    if error.name is None or not error.name.startswith("google"):
        raise
    raise ImportError(
        "Gmail support requires the optional dependencies; "
        'install pintos-utils with the "gmail" extra.'
    ) from error

__all__ = ["GMAIL_SEND_SCOPE", "GmailEmailSender"]
