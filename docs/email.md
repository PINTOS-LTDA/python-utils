# Email API

`pintos-utils` exposes provider-neutral message models and the `EmailSender`
contract from `pintos_utils.email`. Gmail is an optional adapter. Applications
can inject another implementation of the same contract without changing the
code that builds messages.

## Installation

Install the published base package from PyPI:

```bash
python -m pip install pintos-utils
uv add pintos-utils
```

For Gmail support, request the optional extra:

```bash
python -m pip install "pintos-utils[gmail]"
uv add "pintos-utils[gmail]"
```

Install the base package from a checkout with pip or uv:

```bash
python -m pip install .
uv pip install .
```

For editable development with Gmail support:

```bash
python -m pip install -e ".[gmail]"
uv pip install -e ".[gmail]"
```

The base package has no third-party runtime dependencies. The `gmail` extra
installs the Google API and authentication libraries. Importing
`pintos_utils.email` does not load them. Import the adapter explicitly when the
extra is installed:

```python
from pintos_utils.email.providers.gmail import GmailEmailSender
```

For an authorized private SSH Git repository, use a reviewed tag or, for a
reproducible production pin, a full commit hash:

```bash
python -m pip install "pintos-utils[gmail] @ git+ssh://git@<git-host>/<org>/pintos-utils.git@<full-commit-sha>"
uv add "pintos-utils[gmail] @ git+ssh://git@<git-host>/<org>/pintos-utils.git@<full-commit-sha>"
```

Replace the placeholders with the repository location and revision. SSH agent,
deploy key, or the environment's Git credential helper must already grant
access. Do not put passwords or tokens in the URL or committed dependency
configuration.

## Public contract

The provider-neutral API exports:

- `EmailAddress(address, display_name=None)`
- `EmailAttachment(filename, content, content_type=None)`
- `EmailMessage(sender, subject, to=(), cc=(), bcc=(), text_body=None, html_body=None, attachments=())`
- `EmailSender`, a structural protocol with `send(message, /) -> SendResult`
- `SendResult(provider, provider_message_id=None)`
- `EmailError`, `EmailValidationError`, `EmailConfigurationError`,
  `EmailAuthenticationError`, and `EmailProviderError`

Models are frozen dataclasses. Recipient and attachment collections are stored
as tuples. At least one recipient across To, CC, and BCC and at least one body
format are required. Supplying both text and HTML sends them as alternatives.
Header line breaks are rejected. Attachments are passed as in-memory bytes; the
library does not read paths.

```python
from pintos_utils.email import EmailAddress, EmailAttachment, EmailMessage

message = EmailMessage(
    sender=EmailAddress("reports@example.com", "Reports"),
    to=(EmailAddress("person@example.net"),),
    cc=(EmailAddress("team@example.net"),),
    bcc=(EmailAddress("archive@example.net"),),
    subject="Monthly report",
    text_body="The report is attached.",
    html_body="<p>The report is attached.</p>",
    attachments=(
        EmailAttachment("report.csv", csv_bytes, "text/csv"),
        EmailAttachment("chart.png", image_bytes, "image/png"),
    ),
)
```

## Gmail OAuth and sending

The application owns OAuth client configuration, the initial consent flow,
refresh-token persistence, and secret storage. It passes configured Google
credentials to the adapter. Request the narrow
`https://www.googleapis.com/auth/gmail.send` scope, available as
`GMAIL_SEND_SCOPE`. Google Auth refreshes an invalid access token when a refresh
token is available; this library does not start an interactive OAuth flow or
persist tokens.

```python
from google.oauth2.credentials import Credentials

from pintos_utils.email.providers.gmail import (
    GMAIL_SEND_SCOPE,
    GmailEmailSender,
)

credentials = Credentials(
    token=access_token,
    refresh_token=refresh_token,
    token_uri=token_uri,
    client_id=client_id,
    client_secret=client_secret,
    scopes=[GMAIL_SEND_SCOPE],
)
sender = GmailEmailSender(credentials)
result = sender.send(message)
```

`SendResult` means Gmail accepted the request. It does not confirm final delivery
to every recipient. The result includes `provider == "gmail"` and may include an
opaque `provider_message_id`.

## Errors and retry policy

Invalid local message data raises `EmailValidationError`. Missing or unusable
credentials raise `EmailConfigurationError` or `EmailAuthenticationError`.
Provider or transport failures raise `EmailProviderError`, with a stable
`provider` value and `retryable: bool | None` advisory. The original SDK or
transport error is chained as `__cause__`; its text and raw response are not
copied into the library exception message.

For Gmail, known temporary quota/backend responses are classified as retryable,
known permanent rejections as non-retryable, and unclassified or transport
failures as unknown. The adapter never retries automatically. A timeout can
occur after Gmail accepted the message, so the consuming application must
consider duplicate-send risk before retrying.

All providers implement the same small contract:

```python
from pintos_utils.email import EmailMessage, EmailSender, SendResult


def send_report(sender: EmailSender, message: EmailMessage) -> SendResult:
    return sender.send(message)
```

The Gmail SDK, request objects, MIME payload, HTTP status codes, and provider
message identifier details remain inside the adapter boundary.

## Versioning

The package uses Semantic Versioning. Version `1.0.0` is the first stable public
API release, after implementation, validation, and API compatibility review.
Compatible fixes increment patch, compatible additions increment minor, and
breaking public API changes increment major.

The compatibility boundary includes the names and signatures exported by
`pintos_utils.email`, the `GmailEmailSender` and `GMAIL_SEND_SCOPE` adapter
exports, validation behavior, exception categories, retryability semantics, and
the meaning of `SendResult`. Gmail request objects, HTTP parsing, MIME assembly,
and Google SDK types remain implementation details. Future provider adapters
can be added without changing the shared contract; a change to that contract's
existing behavior requires a major version.
