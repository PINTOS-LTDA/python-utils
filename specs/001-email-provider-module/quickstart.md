# Proposal Quickstart: pintos-utils Email

**Status**: Proposed consumer guide; commands become executable after package
implementation and approval.

## Install from a local checkout

```bash
uv pip install .
```

Install editably while developing the library:

```bash
uv pip install -e .
```

Install the local checkout with Gmail support:

```bash
uv pip install -e ".[gmail]"
```

The base install does not include Google client libraries. `gmail` adds the
dependencies required by the Gmail adapter.

## Install from a private Git repository

Use SSH access already configured for the consuming environment. Replace the
host, organization, repository, and revision placeholders:

```bash
uv add "pintos-utils[gmail] @ git+ssh://git@<git-host>/<org>/pintos-utils.git@<full-commit-sha>"
```

The project may instead pin a reviewed release tag, such as `@v1.0.0`. A full
commit hash gives a fixed source revision. Do not put a token or password in the
URL or in committed configuration.

## Compose and send a message

```python
from google.oauth2.credentials import Credentials

from pintos_utils.email import EmailAddress, EmailAttachment, EmailMessage
from pintos_utils.email.providers.gmail import GmailEmailSender

# Values come from the consuming application's secure configuration/storage.
credentials = Credentials(
    token=access_token,
    refresh_token=refresh_token,
    token_uri=token_uri,
    client_id=client_id,
    client_secret=client_secret,
)

sender = GmailEmailSender(credentials)
message = EmailMessage(
    sender=EmailAddress("reports@example.com", "Reports"),
    to=(EmailAddress("person@example.net"),),
    cc=(EmailAddress("team@example.net"),),
    bcc=(EmailAddress("archive@example.net"),),
    subject="Monthly report",
    text_body="The report is attached.",
    html_body="<p>The report is attached.</p>",
    attachments=(
        EmailAttachment(
            filename="report.csv",
            content=csv_bytes,
            content_type="text/csv",
        ),
    ),
)

result = sender.send(message)
print(result.provider, result.provider_message_id)
```

The application performs initial OAuth authorization, stores refresh tokens
securely, and supplies configured Google credentials. The Gmail adapter uses the
`gmail.send` scope and refreshes the access token when Google Auth requires it.

## Handle failures

```python
from pintos_utils.email import EmailAuthenticationError, EmailProviderError

try:
    result = sender.send(message)
except EmailAuthenticationError:
    # Ask the application to reauthorize or replace credentials.
    raise
except EmailProviderError as error:
    # Use error.retryable only as guidance; do not blindly resend an uncertain
    # request because the provider may already have accepted it.
    raise
```

`SendResult` means the provider accepted the request. It does not confirm final
delivery. The public contract and error details are specified in
[`contracts/python-api.md`](contracts/python-api.md).

## Planned local quality gates

After implementation, the project plan will configure these commands:

```bash
uv run pytest --cov=pintos_utils
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```

Unit tests use fake provider clients and transports; they do not need Gmail
credentials or network access.
