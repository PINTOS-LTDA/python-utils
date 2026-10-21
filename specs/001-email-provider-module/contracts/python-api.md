# Proposed Public Python Contract

**Status**: Proposal for review. These names and signatures are not implemented
until this specification is approved.

## Provider-Neutral Imports

```python
from pintos_utils.email import (
    EmailAddress,
    EmailAttachment,
    EmailAuthenticationError,
    EmailConfigurationError,
    EmailError,
    EmailMessage,
    EmailProviderError,
    EmailSender,
    EmailValidationError,
    SendResult,
)
```

The shared module MUST NOT import or expose Google client types.

## Contract

```python
from typing import Protocol

class EmailSender(Protocol):
    def send(self, message: EmailMessage, /) -> SendResult: ...
```

The protocol is structural: consumers can inject a Gmail adapter or another
implementation without registering it globally or using a factory.

## Message Models

```python
@dataclass(frozen=True, slots=True)
class EmailAddress:
    address: str
    display_name: str | None = None

@dataclass(frozen=True, slots=True)
class EmailAttachment:
    filename: str
    content: bytes
    content_type: str | None = None

@dataclass(frozen=True, slots=True)
class EmailMessage:
    sender: EmailAddress
    subject: str
    to: tuple[EmailAddress, ...] = ()
    cc: tuple[EmailAddress, ...] = ()
    bcc: tuple[EmailAddress, ...] = ()
    text_body: str | None = None
    html_body: str | None = None
    attachments: tuple[EmailAttachment, ...] = ()

@dataclass(frozen=True, slots=True)
class SendResult:
    provider: str
    provider_message_id: str | None = None
```

Constructing `EmailMessage` MUST raise `EmailValidationError` if it has no
recipient, no body, or unsafe header line breaks. Public dataclasses are
immutable; collections are tuples. These signatures are the proposed API and can
be adjusted before approval.

## Gmail Adapter

```python
from google.auth.credentials import Credentials

GMAIL_SEND_SCOPE: str

class GmailEmailSender:
    def __init__(self, credentials: Credentials) -> None: ...

    def send(self, message: EmailMessage, /) -> SendResult: ...
```

Import this adapter only when the `gmail` extra is installed:

```python
from pintos_utils.email.providers.gmail import (
    GMAIL_SEND_SCOPE,
    GmailEmailSender,
)
```

The consumer creates/configures and persists credentials. The adapter refreshes
access tokens through Google Auth when needed; it does not perform initial OAuth
consent, read credential files, or persist tokens. The shared `EmailSender`
contract has no Google dependency.

## Exceptions and Error Semantics

- `EmailError` is the base type.
- `EmailValidationError` is raised before provider I/O.
- `EmailConfigurationError` reports missing or unusable provider configuration.
- Importing the Gmail adapter without its optional dependencies raises a clear
  `ImportError` that directs the consumer to install the `gmail` extra.
- `EmailAuthenticationError` reports rejected or unrefreshable credentials.
- `EmailProviderError` reports provider/API/network failures and exposes the
  provider plus an advisory `retryable: bool | None` classification. It
  indicates whether provider documentation recommends retrying the operation;
  it does not guarantee that retrying `send` is duplicate-safe, and the library
  never retries automatically. For Gmail, apply explicit HTTP status and reason
  mappings before the unknown-error fallback. Classify HTTP 429 and HTTP 500,
  502, 503, or 504 as `True`, even when the provider reason is missing or
  unrecognized. Classify HTTP 403 as `True` for `rateLimitExceeded` or
  `userRateLimitExceeded`, and `False` for `dailyLimitExceeded` or `domainPolicy`;
  use `None` for other or missing HTTP 403 reasons. Classify HTTP 400
  `badRequest` and other known permanent rejections as `False`. Map
  authentication failures to `EmailAuthenticationError`. Use `None` for
  unclassified HTTP statuses, other unrecognized status/reason combinations,
  or when no authoritative HTTP response is available.
- Provider exceptions are chained as `__cause__`; their SDK types do not become
  part of consumer control flow.
- No send is retried automatically. A request timeout may leave acceptance
  uncertain, so retry policy remains with the consumer.

## Public API Stability

The provider-neutral names are the compatibility boundary. Gmail request
objects, raw MIME/base64 payloads, HTTP status codes, Gmail `threadId`, and
Google SDK exceptions are private to the adapter. Future SMTP or Microsoft Graph
adapters must implement the same `EmailSender` contract and return the same
`SendResult` model.
