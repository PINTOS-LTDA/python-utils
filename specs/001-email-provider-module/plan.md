# Implementation Plan: Provider-Neutral Email Module

**Branch**: `001-email-provider-module` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-email-provider-module/spec.md`

## Summary

Establish the `pintos-utils` Python package and its first email module. Expose
typed provider-neutral message models, a minimal `EmailSender` protocol,
structured results, and library-owned exceptions. Add Gmail as an optional
adapter that accepts application-configured Google OAuth credentials, delegates
access-token refresh to Google Auth, and serializes MIME messages for
`users.messages.send`. Keep consumer code independent of Google SDK types and
avoid OAuth consent, secret storage, automatic retries, and other providers in
this feature.

## Technical Context

**Language/Version**: Python >= 3.11  
**Primary Dependencies**: No base runtime dependencies; optional `gmail` extra:
`google-api-python-client`, `google-auth`, `google-auth-httplib2`  
**Build System**: Hatchling configured in `pyproject.toml`  
**Environment and Locking**: uv, with a checked-in `uv.lock` for reproducible development  
**Development Dependencies**: pytest, pytest-cov, Ruff, mypy in the `dev` dependency group  
**Storage**: None in the package; OAuth credential persistence belongs to the consuming application  
**Testing**: pytest with pytest-cov; fake Google client/transport; no network in the default suite  
**Target Platform**: Python 3.11+ on supported platforms for the selected Google dependencies  
**Project Type**: Reusable library  
**Performance Goals**: No numeric latency target in this feature; avoid extra provider calls and avoid loading attachment files from paths inside the library  
**Constraints**: Synchronous API; no web framework; no implicit OAuth flow; no automatic send retries; public API remains provider-neutral  
**Scale/Scope**: One provider (Gmail), one send operation, multiple recipients/content alternatives/attachments; SMTP and Microsoft Graph are future adapters

## Constitution Check

| Principle | Plan assessment |
|---|---|
| I. Library-First and Framework Independence | Pass: pure importable package; no framework or application entrypoint. |
| II. Stable, Typed Public API | Pass: explicit `pintos_utils.email` exports, `py.typed`, docs, and SemVer release gate. |
| III. Explicit Boundaries and Proportional Dependency Injection | Pass: `EmailSender` protocol and neutral models; Gmail maps at the infrastructure boundary; consumer injects the adapter. |
| IV. Optional Integrations and Secure Defaults | Pass: empty base runtime dependencies; Gmail extra; consumer owns credential creation/storage; no secrets or content logged. |
| V. Verification and Documentation | Pass: network-free fake-backed tests, pytest-cov, Ruff, mypy, and consumer documentation are planned. |

**Implementation gate**: The user approved the specification and plan. The gate
is complete and implementation is authorized.

## Research Decisions

See [research.md](research.md) for sources and alternatives. Principal decisions:

- Create MIME messages using the Python standard library and submit the encoded
  message through Gmail's `users.messages.send` method.
- Require only `https://www.googleapis.com/auth/gmail.send` for this operation.
- Accept configured Google `Credentials`; do not own the OAuth consent flow or
  durable refresh-token storage.
- Normalize provider errors, return provider acceptance and an opaque optional
  message ID, and do not retry sends automatically.
- Keep core dependencies empty and provide Google libraries through the
  `gmail` extra.
- Support local/editable installs and private Git references over SSH; pin
  production use to a reviewed tag or full commit hash.

## Architecture

```text
Consumer application
  ├── depends on EmailMessage, EmailSender, SendResult, and EmailError types
  └── injects GmailEmailSender at its composition root
          ├── receives configured Google Credentials
          ├── builds the Gmail client and refreshes credentials via Google Auth
          ├── converts the message to MIME and base64url
          ├── calls users.messages.send(userId="me")
          └── maps Gmail response/errors to pintos-utils result/errors
```

The `EmailSender` protocol in `contracts.py` is the service boundary. No second
`EmailService` forwarding wrapper, provider registry, or generic factory is
proposed: the use case is a single send operation with no orchestration, and
consumers can inject an implementation directly. This keeps the service
contract, models, and infrastructure separate without adding a layer that only
forwards arguments.

### Responsibility Boundaries

- `models.py`: immutable, provider-neutral message, address, attachment, and
  result data; validates minimum message invariants before provider I/O.
- `contracts.py`: small synchronous `EmailSender` protocol.
- `exceptions.py`: public error hierarchy and stable retryability semantics.
- `providers/gmail/`: optional Google SDK imports, OAuth credential use, MIME
  conversion, API calls, Gmail response/error translation.
- `tests/`: model/contract/provider unit tests using fakes and mocks; no live API
  suite is required for normal validation.
- `docs/email.md`: installed dependency options, OAuth responsibility boundary,
  usage, errors, and result meaning.

### SOLID Decisions

- **Single Responsibility**: models, contract, errors, and provider adapter have
  distinct responsibilities.
- **Open/Closed and Liskov Substitution**: new providers implement the same
  `EmailSender` behavior and return the same `SendResult` without changing
  consumers.
- **Interface Segregation**: the public protocol exposes only `send`.
- **Dependency Inversion**: consuming code depends on the protocol and receives
  the provider through constructor/application composition.

## Dependency Proposal

| Category | Packages | Reason |
|---|---|---|
| Build backend | `hatchling` | Create wheel and source distribution from `src/`. |
| Base runtime | None | Keep SMTP/other consumers and core models free of third-party dependencies. |
| Optional `gmail` extra | `google-api-python-client`, `google-auth`, `google-auth-httplib2` | Gmail API calls, typed OAuth credentials, and authorized HTTP transport. |
| Development group | `pytest`, `pytest-cov`, `ruff`, `mypy` | Unit testing, coverage measurement, lint/format, and static typing. |
| Environment manager | `uv` | Create/sync the development environment, maintain `uv.lock`, run tools, and build. |

Do not include `google-auth-oauthlib`: the proposed library does not run the
initial consent flow. Use standard-library `email` and `base64` modules for MIME
assembly. Declare supported dependency ranges in project metadata and commit the
uv lockfile; do not pin a resolved transitive snapshot in the public runtime
metadata.

## Distribution and Versioning

- Distribution name: `pintos-utils`; import name: `pintos_utils`.
- The local install uses `uv pip install .`; editable development uses
  `uv pip install -e .` or `uv pip install -e ".[gmail]"`.
- Private Git consumers use a PEP 508 VCS requirement with `git+ssh`, optionally
  selecting `[gmail]`. Document a release tag for review and a full commit hash
  for reproducible production pins. Credentials come from SSH agent/deploy key
  or a configured credential helper, never from the URL.
- Start package development at `0.1.0`; publish `1.0.0` once this approved public
  contract is implemented and validated as stable. After 1.0.0, patch releases
  remain compatible, minor releases add compatible API, and major releases may
  break the public API.
- Include `py.typed` so downstream type checkers can use package annotations.

## Implementation Phases (After Approval)

1. **Package foundation**: Create `pyproject.toml`, source layout, uv environment
   and lockfile, optional extras, tool configuration, and typed public exports.
2. **Provider-neutral contract**: Implement immutable models, validation,
   `EmailSender`, results, and public exceptions with network-free tests.
3. **Gmail adapter**: Build MIME alternatives and attachments; inject configured
   credentials; map Gmail request, response, refresh, and provider errors.
4. **Consumer documentation and packaging**: Document API, OAuth ownership,
   failure semantics, extras, and local/editable/private Git installation; build
   wheel and source distribution and verify install paths.
5. **Release readiness**: Run unit tests, coverage, Ruff, mypy, and package build;
   approve the stable API release version only after compatibility review.

## Project Structure

```text
pyproject.toml
uv.lock
.python-version
README.md
docs/
└── email.md
src/
└── pintos_utils/
    ├── __init__.py
    ├── py.typed
    └── email/
        ├── __init__.py
        ├── contracts.py
        ├── exceptions.py
        ├── models.py
        └── providers/
            ├── __init__.py
            └── gmail/
                ├── __init__.py
                ├── sender.py
                └── _mime.py
tests/
└── unit/
    └── email/
        ├── fakes.py
        ├── test_models.py
        ├── test_contract.py
        └── providers/
            └── gmail/
                ├── test_sender.py
                └── test_mime.py
specs/
└── 001-email-provider-module/
    ├── spec.md
    ├── plan.md
    ├── research.md
    ├── data-model.md
    ├── quickstart.md
    ├── contracts/
    ├── checklists/
    └── tasks.md
```

**Structure Decision**: One Python distribution with independent modules under
`src/pintos_utils`. The Gmail adapter stays behind an explicit provider import
so importing `pintos_utils.email` works without the Gmail extra. The proposed
`contracts.py` is the service port; a separate `services/` folder would only add
a forwarding layer at this stage.

## Type Checking and Error Boundary

- Configure mypy for strict checks on maintained source. Google API client
  discovery objects are dynamic; isolate any necessary `Any` or `cast` at the
  Gmail adapter boundary and keep the public contract fully typed.
- Map invalid MIME/request input to validation errors where detected locally;
  map rejected or failed refresh credentials to `EmailAuthenticationError`;
  map other Google API/transport failures to `EmailProviderError`. The advisory
  `retryable` value indicates whether provider documentation recommends retrying;
  it does not guarantee that retrying `send` is duplicate-safe, and the library
  never retries automatically. For Gmail, apply explicit HTTP status and reason
  mappings before the unknown-error fallback. Set it to `True` for HTTP 429 and
  HTTP 500, 502, 503, or 504, even when the provider reason is missing or
  unrecognized. For HTTP 403, set it to `True` for reason `rateLimitExceeded` or
  `userRateLimitExceeded`, `False` for `dailyLimitExceeded` or `domainPolicy`,
  and `None` for other or missing reasons. Set it to `False` for HTTP 400
  `badRequest` and other known permanent rejections. Map authentication failures
  to `EmailAuthenticationError`. Use `None` for unclassified HTTP statuses,
  other unrecognized status/reason combinations, or when no authoritative HTTP
  response is available.
- Preserve the original exception as `__cause__`, but do not expose raw body,
  OAuth token, or recipient data through default logs/error strings.
- No automatic retry is included because a timeout can leave acceptance
  uncertain.

## Complexity Tracking

No constitution violations or extra architectural layers are proposed. There is
no justification for a provider registry, global service locator, OAuth browser
flow, or separate forwarding service in this first module.
