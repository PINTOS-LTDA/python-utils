# Implementation Plan: PyPI Release Automation

**Branch**: `002-pypi-trusted-publishing` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-pypi-trusted-publishing/spec.md`

## Summary

Prepare `pintos-utils` for public PyPI distribution through a GitHub Actions release workflow that accepts only published stable releases tagged `vMAJOR.MINOR.PATCH`. The workflow will compare the tag to the static `[project].version`, reject an already-published version, run the existing quality gates, and build a wheel and source distribution from the tag's source revision.

The workflow will separate validation/build from upload. A protected GitHub environment named `pypi` will gate a minimal publishing job that receives job-scoped OIDC permission and publishes the already-built files through the PyPA publishing action. No long-lived PyPI token will be configured. PyPI publish attestations will be retained for each uploaded distribution. Package metadata, MIT license text, consumer installation instructions, and release-operator documentation will be completed before the first release.

## Technical Context

**Language/Version**: Python >=3.11; release quality workflow runs on Python 3.11, the declared minimum.

**Primary Dependencies**: Existing uv-managed project, Hatchling build backend, pytest, pytest-cov, Ruff, and mypy. GitHub Actions will use pinned actions for checkout, uv setup, artifact transfer, and `pypa/gh-action-pypi-publish`. No new runtime dependency is required.

**Storage**: No application storage. GitHub Actions artifacts transfer the exact built distributions between jobs; PyPI stores release files and attestations.

**Testing**: Reuse the project gates: pytest with coverage, Ruff lint, Ruff format check, mypy over `src/` and the release-preflight helper, and `uv build --no-sources`. Add deterministic checks that the versioned tag matches project metadata and that both expected distributions carry the same name/version and approved license metadata. Unit tests for the release-version preflight use mocked HTTP responses for existing, absent, and inconclusive versions; the default test suite remains offline.

**Target Platform**: GitHub Actions on GitHub-hosted Ubuntu runners; distributions published to public PyPI. The library is pure Python and will publish one platform-independent wheel plus an sdist.

**Project Type**: Python library with CI and release automation.

**Performance Goals**: No runtime performance target applies. Release validation must finish before the protected publication job is offered for approval.

**Constraints**: Do not change consumer-facing runtime APIs or add base runtime dependencies. Only the isolated publication job may have `id-token: write`; pull-request, branch-validation, release-validation, and build jobs must not. No static PyPI token, manual upload fallback, prerelease release, or TestPyPI path is in scope. Workflow actions must be pinned to full commit SHAs and have the reviewed version noted beside the pin.

**Scale/Scope**: One distribution (`pintos-utils`), one GitHub repository (`PINTOS-LTDA/python-utils`), one dedicated workflow (`.github/workflows/release.yml`), and one protected environment (`pypi`). Preserve the optional `gmail` extra and existing private-Git installation guidance while adding PyPI installation instructions.

## Constitution Check

### Before Phase 0 research

- **Library-first and framework independence**: PASS. This feature changes distribution automation and documentation; it adds no framework or runtime service.
- **Stable, typed public API**: PASS. No public Python symbols or API compatibility behavior change.
- **Explicit boundaries and proportional dependency injection**: PASS. No application contracts or infrastructure abstractions are introduced.
- **Optional integrations and secure defaults**: PASS. The base package remains dependency-free at runtime; the Gmail SDK remains optional. No long-lived publishing secret is introduced.
- **Verification and documentation**: PASS. Release CI will run configured static/unit checks and build both package formats; release and installation instructions are part of the scope.
- **Additional constraints**: PASS. Keep Python >=3.11, `src/`, Hatchling, uv, SemVer, and existing package identity.

### After Phase 1 design

PASS. The design keeps package build and validation separate from PyPI authorization, scopes OIDC permission to the publisher job, uses a protected environment, preserves existing consumer contracts, and adds no unjustified application layer or runtime dependency.

**Operational prerequisite**: GitHub required reviewers for environments depend on repository visibility and account plan. If this repository remains private, the maintainer must confirm that its plan enables required reviewers before the release workflow can satisfy FR-005. If the current plan does not, upgrade the plan before publication; do not silently remove the approval requirement.

## Project Structure

### Documentation (this feature)

```text
specs/002-pypi-trusted-publishing/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── pypi-release.md
│   └── distribution.md
├── checklists/requirements.md
└── tasks.md                 # Produced by the later $speckit-tasks phase
```

### Source and release files (repository root)

```text
.github/
└── workflows/
    ├── ci.yml                # PR/branch checks; no publishing identity
    ├── _quality.yml          # Shared, non-publishing quality workflow
    └── release.yml           # Dedicated GitHub Release -> PyPI workflow
LICENSE                      # MIT text with rights-holder name/year
pyproject.toml                # PEP 639 license and PyPI project URLs/metadata
uv.lock                       # Locked development/build-tool changes, if needed
README.md                     # Base and Gmail-extra PyPI installation
docs/
├── email.md                  # Keep provider usage; align installation examples
└── releases.md               # One-time setup, release, and failure recovery
src/pintos_utils/                 # No runtime implementation changes planned
scripts/
└── release_preflight.py          # Small, typed release-version check used by GitHub Actions
tests/
└── unit/
    └── test_release_preflight.py # Offline tests with mocked registry responses
```

**Structure Decision**: Retain the existing single Python `src/` library. Add two user-facing workflow entry points (`ci.yml`, `release.yml`) and one local reusable workflow for the identical quality gate, so CI and release validation cannot drift. Only `release.yml` is registered as the PyPI Trusted Publisher; `_quality.yml` and `ci.yml` never request OIDC. Package metadata remains in the existing `pyproject.toml`; no new application package, CLI, or release service is justified.

## Release Workflow Design

1. **Continuous validation**: `ci.yml` runs for pull requests and ordinary branch pushes and calls `_quality.yml`. The reusable workflow runs the existing pytest/coverage, Ruff lint/format, mypy, and package-build checks on Python 3.11. It has read-only repository access and no OIDC permission.
2. **Release trigger and validation**: `release.yml` runs for a GitHub Release `published` event. It rejects prereleases and tags not matching stable `vMAJOR.MINOR.PATCH`. A no-credential validation job runs `scripts/release_preflight.py`, which checks that stripping the leading `v` gives the exact `[project].version` from the tagged checkout and queries the version-specific PyPI JSON endpoint. An existing version or an inconclusive network/API error stops the run for maintainer review. A project-level JSON 404 does not prove that the distribution name is available or owned by the intended maintainer. Before the first release, the operator configures the exact pending publisher and reviews PyPI name eligibility as documented. PyPI's first-use project creation and publisher authentication are authoritative; rejection stops before upload. The exact tag checkout is used for following jobs.
3. **Release quality and build**: The release workflow calls `_quality.yml` for the same tagged revision, which runs all quality gates, builds both distributions with `uv build --no-sources`, and verifies their names/version and license metadata/file. On the release call, it uploads `dist/` as a workflow artifact; the ordinary CI call does not retain the artifact. The quality/build job has no `id-token: write`.
4. **Publication approval and upload**: `publish` depends on successful validation and quality/build, references GitHub environment `pypi`, and grants `id-token: write` only at the job level. The job downloads the artifact and calls `pypa/gh-action-pypi-publish` once. It has no checkout, package build, test, arbitrary project script, PyPI token, or unrelated action. PyPI Trusted Publisher configuration binds owner `PINTOS-LTDA`, repository `python-utils`, workflow filename `release.yml`, and environment `pypi`. Before release, the operator compares the effective PyPI publisher configuration with these job claims and confirms no other publisher is configured for `pintos-utils`; any mismatch blocks release readiness. Verify the rejected protected-environment path without uploading. Do not invoke the publishing action with a different project or distribution as a negative test.
5. **Provenance and recovery**: Keep the PyPA action's default PyPI publish attestations enabled for each distribution. After a successful upload, the operator verifies both files and their publisher/source provenance on PyPI. Since PyPI accepts files one at a time, a failed upload can be partial: mark that release run incomplete, inspect PyPI before retrying, and never retry blindly or attempt to replace an already-uploaded file.

The GitHub release event's `GITHUB_SHA` and `GITHUB_REF` identify the last commit and tag for the published release. The workflow must validate the event tag directly and build from that exact revision. A repository ruleset should restrict creation and modification of stable `v*` tags to release maintainers. The `pypi` environment should also restrict eligible deployment refs to the stable release tag pattern where GitHub's environment rules permit it.

## Metadata and Consumer Documentation

- Keep the static project version as the source of truth; do not add a VCS version plugin. The tag/version comparison is an explicit gate and avoids introducing another build dependency.
- Declare the selected license using PEP 639 metadata (`license = "MIT"`, `license-files = ["LICENSE"]`) and retain Hatchling >=1.27. The full MIT text must include the accurate rights-holder name and year supplied by the authorized owner before first publication.
- Ensure PyPI metadata includes the existing name, version, README, Python minimum, description, Gmail optional extra, and source repository URL. Do not invent author details. Include only project URLs that exist and are correct.
- Update README and email documentation with base `pintos-utils` and optional `pintos-utils[gmail]` PyPI installs. Preserve local, editable, and private Git install instructions.
- Add `docs/releases.md` with exact Trusted Publisher values, environment/reviewer setup, stable tag and version procedure, first-project/pending-publisher setup, approval flow, provenance checks, and a no-blind-retry recovery procedure.

## Complexity Tracking

No constitution violations or additional architecture layers are proposed. The one reusable workflow is justified because the same release quality gate must run for both PR/branch CI and the tagged release without separate command definitions.
