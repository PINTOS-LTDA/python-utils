# Research: Provider-Neutral Email Module

**Date**: 2026-10-21  
**Scope**: Decisions needed to prepare the implementation proposal; no service is implemented in this phase.

## Decisions

### Gmail request and MIME representation

- **Decision**: Build an RFC-compliant MIME message with Python's standard
  `email` package, encode it as URL-safe base64, and submit it using Gmail's
  `users.messages.send` method. The adapter maps the returned Gmail message ID
  to the opaque optional ID in `SendResult`.
- **Rationale**: Gmail accepts the message in its `raw` field, and its send method
  takes recipients from the To, Cc, and Bcc headers. Keeping MIME construction
  and response mapping inside the adapter avoids exposing Gmail request objects
  in the library contract.
- **Alternatives considered**: Require consumers to build MIME, or expose Gmail's
  request and response model. Both would couple consumers to one provider.
- **Sources**: [Create and send messages](https://developers.google.com/workspace/gmail/api/guides/sending),
  [users.messages.send](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send).

### OAuth credential ownership and refresh

- **Decision**: Accept already configured Google `Credentials` in the Gmail
  adapter. Delegate access-token refresh to Google Auth and the authorized
  transport. Do not implement an interactive consent flow or persistent token
  store in this package.
- **Rationale**: The consuming application owns OAuth client configuration,
  initial consent, and safe refresh-token storage. Google credentials can refresh
  access tokens; failed refresh is translated to the library's authentication
  exception.
- **Alternatives considered**: Add an OAuth browser/desktop flow and token file
  handling. Those choices would add application policy, secret storage, and
  dependencies that are not common to all consumers.
- **Sources**: [Google Auth OAuth credentials](https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.credentials.html),
  [OAuth 2.0 overview](https://developers.google.com/identity/protocols/oauth2/),
  [Gmail Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python).

### Gmail OAuth scope

- **Decision**: Document `https://www.googleapis.com/auth/gmail.send` as the
  required scope for this provider.
- **Rationale**: The Gmail send method accepts this send-only scope. Broader
  scopes such as `https://mail.google.com/` grant capabilities this module does
  not use. Google classifies `gmail.send` as sensitive, so the consuming
  application's OAuth distribution may require verification.
- **Sources**: [Gmail API OAuth scopes](https://developers.google.com/workspace/gmail/api/auth/scopes),
  [send method authorization](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send),
  [OAuth scope policies](https://developers.google.com/identity/protocols/oauth2/policies).

### Dependencies and optional installation

- **Decision**: Keep core runtime dependencies empty. Define a `gmail` extra with
  `google-api-python-client`, `google-auth`, and `google-auth-httplib2`. Keep
  `google-auth-oauthlib` out because the library does not perform the initial
  OAuth flow. Put pytest, pytest-cov, Ruff, and mypy in a development dependency
  group. Declare Hatchling as the build-system requirement and use uv for the
  development environment and lockfile.
- **Rationale**: The standard library can model and serialize MIME messages;
  provider-specific client libraries are needed only by users of Gmail. uv
  distinguishes published optional extras from local development dependencies.
- **Alternatives considered**: Make Google libraries mandatory, or include
  OAuth-flow packages in the extra. Both add dependencies to use cases that do
  not need them.
- **Sources**: [uv dependency groups and extras](https://docs.astral.sh/uv/concepts/dependencies/),
  [Hatch build configuration](https://hatch.pypa.io/latest/config/build/),
  [Python packaging metadata](https://packaging.python.org/en/latest/specifications/pyproject-toml/).

### Provider boundary and error policy

- **Decision**: Use one small `EmailSender` protocol, shared models, and
  provider-neutral exceptions. Map Google HTTP errors inside the adapter. Do not
  retry sends automatically; expose whether a provider failure is classified as
  retryable so the consuming application can decide.
- **Rationale**: Gmail errors include authentication, invalid request, quota, and
  backend cases. A timeout can occur after acceptance, so a blind resend may
  duplicate a message. Provider SDK exceptions are not a stable cross-provider
  API.
- **Alternatives considered**: Return `False` for failure, leak `HttpError`, or
  retry every transient-looking error. Those options lose useful detail, couple
  callers to Google, or risk duplicates.
- **Sources**: [Gmail API error handling](https://developers.google.com/workspace/gmail/api/guides/handle-errors),
  [users.messages.send](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send).

### Public typing and package layout

- **Decision**: Use a `src/pintos_utils` layout, include `py.typed`, and publish
  one explicit provider-neutral API under `pintos_utils.email`. Type the Gmail
  credential only in its provider adapter. Keep any dynamic Google client typing
  localized to that adapter boundary.
- **Rationale**: The src layout reduces accidental imports from a checkout, and
  `py.typed` marks the installed distribution as typed for consumers. A narrow
  provider seam permits a minimal public contract without a plugin registry.
- **Sources**: [src versus flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/),
  [PEP 561](https://peps.python.org/pep-0561/),
  [Hatch build configuration](https://hatch.pypa.io/latest/config/build/).

### Private Git installation and version policy

- **Decision**: Support PEP 508 direct Git references over SSH and document a
  version tag for review plus a full commit hash for reproducible production
  pins. Never place a credential in the URL. Begin development at `0.1.0`; make
  the API stable and publish `1.0.0` after the approved contract is implemented
  and validated. Then apply SemVer for compatible and breaking changes.
- **Rationale**: pip supports `git+ssh` and tags or commit hashes; uv locks a Git
  dependency to a commit. SemVer reserves the stable public API guarantee for
  `1.0.0` and later.
- **Alternatives considered**: Depend on a mutable branch or claim stability at
  `0.1.0`. A mutable branch harms reproducibility, and pre-1.0 versions signal
  that the API can still change.
- **Sources**: [pip VCS support](https://pip.pypa.io/en/stable/topics/vcs-support/),
  [uv dependency management](https://docs.astral.sh/uv/concepts/dependencies/),
  [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## Remaining Constraints

- Private Git authentication depends on the consuming environment's Git/SSH
  credentials; the package cannot grant repository access itself.
- A successful Gmail API call means the provider accepted the request, not that
  final delivery occurred.
- Unit tests use fake clients and transports. Live Gmail credentials and network
  access are not required for the default test suite.
