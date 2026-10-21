<!--
Sync Impact Report
Version change: template → 1.0.0 (initial ratification)
Modified principles: none; all five project principles established
Added sections: Additional Constraints; Development Workflow
Removed sections: none
Follow-up TODOs: none
-->

# pintos-utils Constitution

## Core Principles

### I. Library-First and Framework Independence
Every capability MUST be usable as a Python library without requiring a web or
application framework. Modules MUST have a clear responsibility and MUST NOT
depend on unrelated modules. The core package MUST remain useful without optional
provider integrations installed.

### II. Stable, Typed Public API
Public contracts MUST be intentional, documented, and statically typed. Public
names MUST be exported from their documented module and covered by compatibility
review. Released versions MUST follow Semantic Versioning: compatible fixes use a
patch release, compatible additions use a minor release, and breaking public API
changes use a major release. The API is considered stable beginning at 1.0.0.

### III. Explicit Boundaries and Proportional Dependency Injection
Contracts and data models MUST remain independent of infrastructure SDKs.
Provider implementations MUST depend on those contracts and translate provider
requests, responses, and errors at the boundary. Dependencies MUST be injected
where doing so enables substitution or deterministic tests. Additional services,
factories, registries, and layers MUST NOT be introduced without a concrete use
case.

### IV. Optional Integrations and Secure Defaults
The base installation MUST have no third-party runtime dependencies. Features
that require external SDKs MUST be provided through named optional extras. Secrets,
tokens, message bodies, and recipient data MUST NOT be written to logs by default.
Integrations MUST request the narrowest permissions needed and MUST leave
credential acquisition and durable secret storage with the consuming application
unless a future approved specification says otherwise.

### V. Verification and Documentation
Public behavior MUST have deterministic unit tests that do not require network
access. Provider adapters MUST be testable with fakes or mocks. Public APIs MUST
include type annotations and consumer-facing documentation. Ruff and mypy checks
MUST cover the maintained source tree, and pytest-cov MUST measure the unit-test
suite.

## Additional Constraints

- The minimum supported Python version is 3.11.
- The distribution name is `pintos-utils`; the import package is `pintos_utils`.
- Source code MUST use the `src/` layout and build through Hatchling configured in
  `pyproject.toml`.
- uv manages the development environment and lockfile. Runtime dependencies and
  optional extras MUST be declared in standard project metadata.
- pytest, pytest-cov, Ruff, and mypy are development tools, not runtime
  dependencies.
- The package MUST NOT add a web framework as a dependency.
- Local, editable, and private Git installation paths MUST be documented. Private
  repository credentials MUST NOT be embedded in dependency URLs or committed
  configuration.

## Development Workflow

- A feature that changes the public API or adds a provider MUST have an approved
  Spec Kit specification and implementation plan before source implementation.
- Implementation tasks MUST identify their target paths and map to approved user
  requirements.
- Unit tests MUST use fakes or mocks for provider and network boundaries. The
  default test suite MUST not contact external services.
- A release MUST build successfully, pass the configured static and unit-test
  checks, include public documentation, and state any API compatibility impact.
- Any exception to these constraints MUST be documented in the relevant plan and
  approved before implementation.

## Governance

This constitution governs project design and review. Amendments MUST include a
version change and a short impact report. Additions or material expansions use a
MINOR bump; removals or redefinitions use a MAJOR bump; wording-only clarification
uses a PATCH bump. Every implementation plan MUST state how it complies with this
constitution. Reviewers MUST resolve conflicts in favor of these principles or
record an approved amendment before implementation. Public API compatibility MUST
be reviewed before each release.

**Version**: 1.0.0 | **Ratified**: 2026-10-21 | **Last Amended**: 2026-10-21
