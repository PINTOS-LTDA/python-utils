# Tasks: Provider-Neutral Email Module

**Input**: Design documents in `/specs/001-email-provider-module/`  
**Prerequisites**: Approved `spec.md` and `plan.md`, plus `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`.

**Implementation gate**: The user approved the specification and plan; these
implementation tasks are authorized.

## Phase 1: Setup

**Purpose**: Establish the package metadata and developer tools.

- [X] T001 Configure package metadata, Hatchling, the optional `gmail` extra, development dependencies, and tool settings in `pyproject.toml`.
- [X] T002 Pin Python 3.11 in `.python-version` and generate the reproducible environment lockfile at `uv.lock` from the approved `pyproject.toml`.
- [X] T003 Add development and distribution guidance to `README.md` and ignore local virtual environments and build artifacts in `.gitignore`.

## Phase 2: Foundational Contract

**Purpose**: Define shared data and errors before provider-specific code.

- [X] T004 Create the typed package structure and marker at `src/pintos_utils/__init__.py`, `src/pintos_utils/py.typed`, `src/pintos_utils/email/__init__.py`, and `src/pintos_utils/email/providers/__init__.py`.
- [X] T005 [P] Write model validation tests for recipients, body alternatives, attachments, and header safety in `tests/unit/email/test_models.py`.
- [X] T006 Implement immutable address, attachment, message, and result types in `src/pintos_utils/email/models.py`.
- [X] T007 [P] Write public exception hierarchy tests in `tests/unit/email/test_exceptions.py`.
- [X] T008 Implement the minimal `EmailSender` protocol and provider-neutral exception hierarchy in `src/pintos_utils/email/contracts.py` and `src/pintos_utils/email/exceptions.py`.

**Checkpoint**: Shared models, validation, and error names are stable before a
provider adapter is added.

## Phase 3: User Story 1 - Send an email through Gmail (Priority: P1)

**Goal**: Submit HTML/text messages with recipients and multiple attachments
using consumer-configured OAuth credentials.

**Independent Test**: A fake Google client and fake refresh transport verify
request construction, success result, refresh behavior, and error mapping without
network access or Gmail credentials.

### Tests for User Story 1

- [X] T009 [P] Write MIME tests for To/CC/BCC mapping, asserting BCC recipients are in Bcc and absent from To/Cc, plus alternative bodies, multiple attachments, and base64url payload in `tests/unit/email/providers/gmail/test_mime.py`.
- [X] T010 [P] Write fake-client send, OAuth refresh, result, error-mapping, and retryability tests asserting HTTP 503 with a missing or unrecognized reason maps to `True`, while HTTP 403 with an unrecognized reason, an unclassified status, and a timeout without an HTTP response map to `None`; also cover mapped retryable, permanent, and authentication errors in `tests/unit/email/providers/gmail/test_sender.py`.

### Implementation for User Story 1

- [X] T011 Implement MIME serialization for text, HTML, and attachments in `src/pintos_utils/email/providers/gmail/_mime.py`.
- [X] T012 Implement `GmailEmailSender`, injected credentials, send-only scope, request/response mapping, and normalized error handling in `src/pintos_utils/email/providers/gmail/sender.py` and `src/pintos_utils/email/providers/gmail/__init__.py`.

**Checkpoint**: The Gmail adapter sends a single composed message through a fake
client and returns `SendResult`; failed refresh and provider failures raise
documented library exceptions.

## Phase 4: User Story 2 - Use a provider-neutral contract (Priority: P1)

**Goal**: Verify consumers can use one contract independently of a concrete
provider SDK.

**Independent Test**: A fake non-Gmail sender accepts the same message and
produces the shared result type; consumer-facing imports do not load Google SDKs.

- [X] T013 Add provider-neutral fake senders, contract conformance tests, and a base-import check for the Gmail extra boundary in `tests/unit/email/fakes.py` and `tests/unit/email/test_contract.py`.
- [X] T014 Verify and document the shared public exports and provider import boundary in `src/pintos_utils/email/__init__.py` and `docs/email.md`.

## Phase 5: User Story 3 - Install the library in consuming projects (Priority: P2)

**Goal**: Document and verify base, editable, and private Git installation with
optional Gmail dependencies.

**Independent Test**: Build a wheel and source distribution, install the local
and editable package, and resolve an authorized pinned Git reference with the
Gmail extra.

- [X] T015 Document local, editable, and private SSH Git installation, OAuth ownership, public API, and error semantics in `docs/email.md` and `README.md`.
- [ ] T016 Verify wheel and source distribution contents, clean local/editable installs, and an authorized pinned Git install with the Gmail extra against `pyproject.toml`, `uv.lock`, and `specs/001-email-provider-module/quickstart.md`.
  Wheel and sdist contents, clean local-wheel and editable installs, Gmail-extra
  imports, and a pinned local Git fixture passed. The pushed private remote now
  exposes commit `8676c28bbf9b174691cb9e7909e1b636ba942a28`, but a pinned install
  from its SSH URL could not be verified here: OpenSSH rejects the host-wide
  `/etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf` because it is world-writable
  (mode 777), and bypassing that config cannot resolve `github.com` in this
  environment. Keep T016 open until the private Git install is verified from an
  environment with working SSH access.

## Final Phase: Quality and Release Readiness

**Purpose**: Complete the approved scope and prepare a stable API release.

- [X] T017 Run the network-free unit suite with coverage using `tests/unit/email/` and `pyproject.toml`.
- [X] T018 Run Ruff and mypy over `src/pintos_utils/` and fix public typing or style gaps in `pyproject.toml` and the affected source files.
- [X] T019 Verify released versions follow FR-016, record the public API compatibility impact, and approve `1.0.0` as the first stable release in `pyproject.toml` and `docs/email.md` for SC-006.

## Dependencies and Execution Order

- Phase 1 precedes all other work.
- Phase 2 provides the public types and exceptions required by User Story 1.
- T005 and T007 may be drafted in parallel after T004 because they cover separate
  test files and independent concerns.
- User Story 1 follows Phase 2. T009 and T010 may be written in parallel because
  they target separate test files; T011 and T012 follow the tests. T012 depends
  on T011 because the Gmail sender uses its MIME serializer.
- User Story 2 verifies the same shared contract after it exists; it does not add
  a second production provider in this feature.
- User Story 3 documentation can proceed once the package and adapter imports
  are decided. Distribution verification follows package metadata and docs.
- Final quality and release review follow all desired stories.

## Implementation Strategy

1. Complete setup and shared contracts.
2. Implement the Gmail adapter behind the approved contract and validate it with
   fake clients and transports.
3. Verify the consumer substitution and installation scenarios.
4. Run local quality gates and approve `1.0.0` only when the public contract is
   stable and the complete scope passes review.

No task requires a live Gmail account or network access. The private Git install
check requires repository access only when exercised in the consuming
environment.

## Phase 6: Convergence

- [ ] T020 Validate the published private Git install at a full commit SHA with the Gmail extra in a clean Python 3.11+ consumer environment, then record evidence needed to complete T016 per SC-004 (partial).
  Retried on 2026-10-21 with a clean Python 3.11.17 virtual environment and
  `UV_CACHE_DIR` under `/tmp`. The remote branch is reachable and points to the
  pinned SHA, but `uv pip install` over SSH still stops because OpenSSH rejects
  the world-writable host config above. Setting `GIT_SSH_COMMAND='ssh -F /dev/null'`
  bypasses that file but then fails DNS resolution for `github.com`. T020 and
  T016 remain open until the pinned install and Gmail imports pass in an
  environment with working SSH and DNS.
