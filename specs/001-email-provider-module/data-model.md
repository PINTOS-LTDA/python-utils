# Data Model: Provider-Neutral Email Module

## EmailAddress

Represents one mailbox and optional display name.

| Field | Type | Required | Rules |
|---|---|---:|---|
| `address` | `str` | Yes | Non-empty; reject CR/LF header injection. The provider may reject unsupported address syntax; the library does not claim the mailbox exists. |
| `display_name` | `str | None` | No | Reject CR/LF header injection. |

## EmailAttachment

Represents one attachment already read by the consuming application.

| Field | Type | Required | Rules |
|---|---|---:|---|
| `filename` | `str` | Yes | Non-empty and safe to serialize as a MIME filename. |
| `content` | `bytes` | Yes | Exact bytes to attach; the library does not read a path. |
| `content_type` | `str | None` | No | MIME type; use `application/octet-stream` when omitted and reject an invalid supplied value. |

## EmailMessage

Immutable input to the provider-neutral sender contract.

| Field | Type | Required | Rules |
|---|---|---:|---|
| `sender` | `EmailAddress` | Yes | Address used in the From header. The provider can reject an unauthorized sender. |
| `subject` | `str` | Yes | May be empty unless a provider rejects it; reject CR/LF. |
| `to` | `tuple[EmailAddress, ...]` | No | Defaults to empty. |
| `cc` | `tuple[EmailAddress, ...]` | No | Defaults to empty. |
| `bcc` | `tuple[EmailAddress, ...]` | No | Defaults to empty and must not be rendered as a visible To/Cc recipient. |
| `text_body` | `str | None` | No | Plain-text alternative. |
| `html_body` | `str | None` | No | HTML alternative. |
| `attachments` | `tuple[EmailAttachment, ...]` | No | Defaults to empty; multiple attachments are supported. |

**Validation**: At least one recipient must exist across To, CC, and BCC. At
least one of `text_body` or `html_body` must be provided. If both are present,
the provider sends them as alternatives for one message. Model validation occurs
before provider I/O.

## SendResult

Represents successful provider acceptance of a send request.

| Field | Type | Required | Rules |
|---|---|---:|---|
| `provider` | `str` | Yes | Stable adapter identifier such as `gmail`. |
| `provider_message_id` | `str | None` | No | Opaque provider-issued ID; consumers must not parse it. |

Returning `SendResult` means the provider accepted the send request. It does not
mean the message was delivered to every recipient.

## Exceptions

| Type | Meaning |
|---|---|
| `EmailError` | Base exception for public email-module failures. |
| `EmailValidationError` | Message or attachment is invalid before a provider call. |
| `EmailConfigurationError` | Required provider configuration is missing or unusable. |
| `EmailAuthenticationError` | Credentials are invalid, cannot refresh, or lack required permission. |
| `EmailProviderError` | Provider rejected or could not confirm the request; includes provider and retryability classification when known. |

Provider SDK errors remain the chained cause for diagnostics; their raw response
body and sensitive message contents are not included in default exception text.
