# Feature Specification: Provider-Neutral Email Module

**Feature Branch**: `001-email-provider-module`  
**Created**: 2026-10-21  
**Status**: Approved for implementation
**Input**: User request to start `pintos-utils` as a reusable Python library and define its first email module around Gmail OAuth 2.0 while keeping the consumer-facing provider contract independent.

## User Scenarios & Testing

### User Story 1 - Send an email through Gmail (Priority: P1)

As an application developer, I can compose an email using common fields and send
it through Gmail using credentials configured by my application.

**Why this priority**: Gmail is the first provider and the primary capability of
the initial library module.

**Independent Test**: A unit test supplies a fake Gmail client and verifies a
successful request and structured result without making a network request.

**Acceptance Scenarios**:

1. **Given** valid credentials and an email with To, CC, BCC, HTML and text
   bodies, and multiple attachments, **When** the application sends it,
   **Then** the provider receives one message containing those fields and the
   caller receives a structured acceptance result.
2. **Given** an expired access token and a usable refresh token, **When** the
   application sends an email, **Then** the credentials are refreshed before the
   provider request.
3. **Given** missing, revoked, or unrefreshable credentials, **When** the
   application sends an email, **Then** it receives a documented authentication
   error and can decide whether to reauthorize.

### User Story 2 - Use a provider-neutral contract (Priority: P1)

As an application developer, I can depend on the same email models, sender
contract, result, and error categories regardless of the selected provider.

**Why this priority**: The public contract must allow future SMTP or Microsoft
Graph adapters without requiring consumer code to depend on Gmail SDK types.

**Independent Test**: A fake provider implements the public sender contract and
accepts the same message model used by the Gmail adapter; provider-specific types
do not appear in the shared contract.

**Acceptance Scenarios**:

1. **Given** a consumer that calls only the shared sender contract, **When** a
   conforming provider is injected, **Then** the consumer uses the same message
   and result types without changing its email composition code.
2. **Given** a provider failure, **When** it crosses the public boundary,
   **Then** the consumer receives a documented library exception rather than a
   provider SDK exception.

### User Story 3 - Install the library in consuming projects (Priority: P2)

As an application developer, I can install the package locally, editably during
development, or from a private Git repository, and install Gmail support only
when needed.

**Why this priority**: Consumers need predictable adoption paths while projects
that do not send Gmail messages avoid its external dependencies.

**Independent Test**: Installation instructions cover a local install, an
editable install, and a private Git reference with the Gmail extra in a clean
Python 3.11-or-newer environment.

**Acceptance Scenarios**:

1. **Given** a local checkout, **When** a consumer installs the base package,
   **Then** the provider-neutral module is importable without Google SDKs.
2. **Given** a private Git repository and authorized Git access, **When** a
   consumer installs a tagged or pinned revision with the Gmail extra,
   **Then** the Gmail adapter and its required dependencies are available.

### Edge Cases

- An email with no To, CC, or BCC recipient is rejected before provider I/O.
- An email with neither an HTML nor text body is rejected; when both are given,
  they are alternatives for the same content.
- Header values containing line breaks are rejected to prevent header injection.
- BCC addresses MUST be included in the submitted message as Bcc recipients and
  MUST NOT appear in To or Cc headers. The library does not claim control over
  provider behavior after submission.
- An omitted attachment media type uses `application/octet-stream`; an invalid
  supplied media type is rejected before sending, and file content is never
  silently dropped.
- Gmail rejects a message because of size, quota, missing permission, disabled
  API, or provider outage; the failure is surfaced through a typed exception.
- A timeout after submission may leave delivery status unknown; the library does
  not retry automatically and risk sending a duplicate.
- A provider response may omit an identifier; the structured result still
  represents provider acceptance without inventing an ID.

## Requirements

### Functional Requirements

- **FR-001**: Consumers MUST be able to describe a sender, subject, one or more
  recipients across To, CC, and BCC, and message content.
- **FR-002**: The message model MUST support HTML and plain-text bodies together
  as alternatives and MUST allow either body to be used by itself.
- **FR-003**: Consumers MUST be able to attach multiple files using a filename,
  media type, and in-memory bytes.
- **FR-004**: The library MUST expose a provider-neutral sender contract that
  accepts the shared message model and returns a structured result.
- **FR-005**: A provider implementation MUST be replaceable without changing the
  shared message, result, or exception contract used by consumers.
- **FR-006**: The Gmail implementation MUST accept OAuth credentials configured
  by the consuming application; initial consent flow and durable credential
  storage are outside the library's responsibility.
- **FR-007**: The Gmail implementation MUST use a valid refresh token to refresh
  an expired access token before sending when required by the authentication
  client.
- **FR-008**: The send result MUST identify the provider and MAY include an
  opaque provider message ID. It MUST indicate provider acceptance only and MUST
  NOT claim final recipient delivery.
- **FR-009**: The library MUST expose documented, provider-neutral exceptions for
  invalid messages, configuration/authentication failures, and provider
  failures; SDK-specific exceptions MUST NOT escape the provider boundary.
- **FR-010**: The default implementation MUST NOT retry a send automatically.
- **FR-011**: Installing the base package MUST NOT install Google SDKs. Gmail
  dependencies MUST be available through a named optional extra.
- **FR-012**: Unit tests for message construction, MIME generation, provider
  request mapping, token refresh behavior, and error mapping MUST run without
  network access.
- **FR-013**: Consumer documentation MUST explain local, editable, and private
  Git installation, including how to request optional Gmail dependencies.
- **FR-014**: Public models, sender contracts, results, exceptions, and examples
  MUST be typed and documented.
- **FR-015**: The library MUST remain independent of web frameworks.
- **FR-016**: Released package versions MUST follow Semantic Versioning. The
  first stable release MUST be `1.0.0` and MUST follow approval of the public API
  contract.

### Key Entities

- **EmailAddress**: An email address with an optional display name.
- **EmailAttachment**: A filename, optional media type, and attachment bytes.
- **EmailMessage**: Sender, To/CC/BCC collections, subject, optional text and
  HTML bodies, and zero or more attachments.
- **EmailSender**: A provider-neutral contract for submitting one message.
- **SendResult**: Provider identity and an optional opaque provider message ID;
  acceptance does not imply delivery.
- **EmailError**: Base library error with documented validation,
  configuration/authentication, and provider-failure categories.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A fake provider request captures To, CC, BCC, both body formats,
  and at least two attachments in one send operation.
- **SC-002**: Unit tests cover successful refresh, failed refresh, provider
  acceptance, and typed error mapping while making zero network requests.
- **SC-003**: A consumer example can call a sender through the shared contract
  without importing a provider SDK in its message-composition code.
- **SC-004**: The installation guide documents and validates base, editable,
  and private Git installation paths for Python 3.11 or newer.
- **SC-005**: Every successful provider call returns a structured result, and
  every failure path covered by the public contract raises a documented library
  exception rather than returning an ambiguous failure value.
- **SC-006**: The release review confirms the package version follows Semantic
  Versioning, records the public API compatibility impact, and approves `1.0.0`
  as the first stable release.

## Assumptions

- The consuming application owns OAuth consent, client secrets, refresh-token
  storage, and the initial authorization flow. The library receives configured
  credentials and delegates access-token refresh to the Google authentication
  client.
- The Gmail adapter requests only the send permission needed for this module.
- The initial API is synchronous because the selected Google API client is
  synchronous; an asynchronous API is not part of this proposal.
- SMTP and Microsoft Graph are future adapters, not implementations in this
  feature. The provider-neutral contract is designed to accommodate them.
- Gmail acceptance is not proof that a recipient received the message.
- The first stable API release will follow implementation and approval of the
  public contracts in this feature.
