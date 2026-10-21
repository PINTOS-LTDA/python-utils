# Feature Specification: PyPI Release Automation

**Feature Branch**: 002-pypi-trusted-publishing
**Created**: 2026-10-21
**Status**: Ready for implementation
**Input**: User request to prepare the pintos-utils library for publication on PyPI using GitHub Actions and Trusted Publishing.

## User Scenarios & Testing

### User Story 1 - Publish an approved library release (Priority: P1)

As a project maintainer, I can turn an approved semantic version into a PyPI release so consumers can install the same reviewed library version from the public package index.

**Why this priority**: A repeatable release path is the main outcome of preparing the library for public distribution.

**Independent Test**: Validate the release workflow with a versioned release candidate, confirm that its source and metadata are checked before upload, then verify a first authorized release can be installed from PyPI.

**Acceptance Scenarios**:

1. **Given** a published GitHub release for a tag matching the package version and all release checks pass, **When** the maintainer approves publication, **Then** the matching source revision is published to PyPI with both a wheel and a source distribution.
2. **Given** a version mismatch, failed quality gate, rejected approval, already-published version, or PyPI rejection of the project name or publisher identity, **When** a release is processed, **Then** publication stops with a clear reason before any new distribution is uploaded.
3. **Given** a pull request or ordinary branch update, **When** its checks run, **Then** no PyPI publication is attempted and no publishing identity is made available to those checks.

### User Story 2 - Authorize publication without a stored PyPI token (Priority: P1)

As a project maintainer, I can authorize only the intended release workflow to publish, without maintaining a long-lived PyPI upload token.

**Why this priority**: Restricting the publisher identity and minimizing credential exposure protects the package and its consumers.

**Independent Test**: Compare the complete PyPI Trusted Publisher configuration for `pintos-utils` with the OIDC claims of the isolated `publish` job in `release.yml` (owner, repository, workflow filename, and environment). Confirm that only the intended publisher is configured and that no static credential fallback exists. Deny a controlled deployment through the protected environment and confirm that no distribution was uploaded. Verify an authorized production release separately, only when explicitly approved.

**Acceptance Scenarios**:

1. **Given** the package owner has configured the intended repository, release workflow, and protected publication environment as a PyPI Trusted Publisher, **When** that workflow requests publication after approval, **Then** PyPI accepts the configured identity without a stored API token.
2. **Given** the repository, workflow, or environment does not match the registered publisher, **When** publication is attempted, **Then** it fails closed without falling back to a static token.
3. **Given** a publication is awaiting the protected environment's required reviewer, **When** approval is denied, **Then** no distribution is uploaded.

### User Story 3 - Install and inspect a published release (Priority: P2)

As a consuming application developer, I can install the base library or its optional Gmail support from PyPI and inspect the release's package information and origin.

**Why this priority**: Public distribution is useful only when consumers can find the correct package, install the desired capabilities, and identify where the release came from.

**Independent Test**: Install the published base distribution and the Gmail extra in clean supported environments, then inspect the PyPI project page and distribution provenance.

**Acceptance Scenarios**:

1. **Given** a successful release, **When** a consumer installs the base package from PyPI, **Then** the documented provider-neutral import is available without Gmail dependencies.
2. **Given** a successful release, **When** a consumer requests the Gmail extra, **Then** the documented Gmail integration and its required dependencies are available.
3. **Given** a release artifact on PyPI, **When** a consumer inspects its provenance, **Then** the source repository, source revision, and authorized publishing workflow match the approved release.
4. **Given** the maintainer has selected the package license, **When** a consumer inspects the release metadata and files, **Then** the declared license and included license text match that approved choice.

### Edge Cases

- A 404 from PyPI's project JSON endpoint does not prove that a package name is available: names can be unavailable without a visible project, and pending publishers do not reserve names. If PyPI rejects the project name or publisher identity at first use, publication must stop without silently changing the distribution name or uploading files.
- A release tag does not match the version declared by the package.
- A version has already been published and cannot be replaced.
- A maintainer rejects the protected-environment approval or the Trusted Publisher identity is misconfigured.
- An upload or provenance step fails after release checks pass; the workflow reports the failure and the maintainer checks PyPI before retrying to avoid an ambiguous or duplicate release.
- One distribution is missing provenance or reports a different source revision from the other distribution.

## Requirements

### Functional Requirements

- **FR-001**: Maintainers MUST be able to initiate a production release by publishing a GitHub release associated with a stable semantic-version tag in the form vMAJOR.MINOR.PATCH.
- **FR-002**: Before publication, the release process MUST verify that the tag version exactly matches the package version and that the version has not already been released.
- **FR-003**: Publication MUST require the project's established release quality checks to pass, including the unit-test, coverage, lint, formatting, type-checking, and package-build checks.
- **FR-004**: Each release MUST contain a wheel and a source distribution built from the exact source revision identified by the release tag, with matching package name and version metadata.
- **FR-005**: A maintainer designated by the project MUST approve the protected production publication environment before PyPI upload begins.
- **FR-006**: PyPI MUST trust only the intended GitHub repository, dedicated release workflow, and protected environment for this package.
- **FR-007**: The release process MUST use PyPI Trusted Publishing and short-lived federated credentials; it MUST NOT require or fall back to a stored long-lived PyPI API token.
- **FR-008**: Only the isolated publication job may request the identity permission needed to publish. Pull-request, branch-validation, and artifact-build jobs MUST NOT receive that publishing permission.
- **FR-009**: The publication process MUST retain PyPI publish provenance for every uploaded distribution, identifying the expected repository, source revision, and release workflow.
- **FR-010**: Before the first release, the public package metadata and included license text MUST accurately describe the package, its supported Python versions, optional Gmail extra, documentation, source repository, and approved license terms.
- **FR-011**: Consumer documentation MUST explain installation from PyPI for both the base package and the optional Gmail extra.
- **FR-012**: Release documentation MUST explain the one-time Trusted Publisher and protected-environment setup, the release steps, version/tag rules, and how to respond to failed or ambiguous publication attempts.
- **FR-013**: Release failures MUST identify whether validation, version checks, approval, publisher authentication, upload, or provenance verification prevented completion, without exposing credentials. Rejection of project creation or publisher authentication on first use MUST stop before any distribution is uploaded.

### Key Entities

- **Release**: An approved semantic version associated with an immutable source revision and a publication status.
- **Distribution**: A wheel or source archive for one release, identified by package name, version, and content digest.
- **Trusted Publisher**: The PyPI authorization binding between a repository owner, repository, release workflow, and protected environment.
- **Release provenance**: Verifiable information connecting each published distribution to its source revision and publishing workflow.

## Success Criteria

### Measurable Outcomes

- **SC-001**: One approved release appears as a single version in the public package index, and consumers can install it with or without optional Gmail support.
- **SC-002**: A version mismatch, failed quality check, rejected approval, unrecognized publisher identity, or PyPI rejection of project creation results in zero new release files.
- **SC-003**: A release completes without requiring or storing a long-lived publishing credential.
- **SC-004**: Every file in a successful release has verifiable provenance matching the source repository, release revision, and authorized publisher, with no missing or inconsistent provenance warning.
- **SC-005**: The release guide contains all publisher-setup inputs and operator actions needed to prepare and execute a release without undocumented repository configuration.

## Assumptions

- The existing package metadata remains the source of truth for the release version; stable release tags use the vMAJOR.MINOR.PATCH form.
- Production publication is the initial target. TestPyPI, prerelease publication, manual uploads, and alternative CI providers are outside the first release scope.
- An authorized project maintainer configures the PyPI Trusted Publisher and GitHub protected environment outside the repository; the repository documentation will identify the exact values and steps. A pending publisher can create a new project on first use but does not reserve its name. A project JSON 404 is not proof of name availability; PyPI's first-use project creation and publisher authentication are authoritative.
- The publication environment requires approval from a maintainer designated by the project.
- **License**: The project will use the MIT License (SPDX identifier MIT). The authorized rights holder will provide the accurate copyright holder name and year in the distributed license text before the first release.
- The requested GitHub Actions and PyPI Trusted Publishing choices are fixed by the project request; the specification focuses on release behavior, authorization, and consumer outcomes.

## External References

- [PyPI Trusted Publishers overview](https://docs.pypi.org/trusted-publishers/)
- [Adding a Trusted Publisher to a PyPI project](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
- [Publishing with a Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- [Choosing a PyPI project name](https://docs.pypi.org/project-management/choosing-a-name/)
- [PyPI provenance and attestations](https://docs.pypi.org/using-pypi/package-security/provenance/)
- [MIT License](https://opensource.org/license/mit)
