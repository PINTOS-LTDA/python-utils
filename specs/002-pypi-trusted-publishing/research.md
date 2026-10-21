# Research: PyPI Release Automation

**Feature**: `002-pypi-trusted-publishing`
**Date**: 2026-10-21

## Decisions

### 1. Trigger the dedicated release workflow from a published GitHub Release

**Decision**: Use `release: types: [published]` in `.github/workflows/release.yml`, then explicitly reject prereleases and validate the release tag against `vMAJOR.MINOR.PATCH`.

**Rationale**: This matches the maintainer action named in the feature specification. GitHub documents that the release event exposes the tag ref and last commit of the tagged release. The `published` event can also fire for a prerelease created from a draft, so checking the release's prerelease flag and enforcing the stable-tag expression are both necessary.

**Alternatives considered**:
- `push.tags: ["v*"]`: suitable when pushing a tag itself is the canonical release action; rejected because the approved spec requires a published GitHub release.
- `workflow_dispatch`: rejected as an unneeded manual publishing path and a larger trusted-workflow surface.

Sources: [GitHub release events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), [PyPI Trusted Publisher setup](https://docs.pypi.org/trusted-publishers/adding-a-publisher/).

### 2. Reuse one non-publishing quality gate and keep publishing in a separate job

**Decision**: Add `ci.yml` for PR/branch checks, a local reusable `_quality.yml` for the shared quality commands, and a dedicated `release.yml`. Release validation and build run without OIDC. The `publish` job only downloads the built artifact and invokes the PyPA publishing action.

**Rationale**: A shared quality workflow prevents CI and release gates from drifting. The publisher remains registered against the top-level `release.yml`; no reusable workflow or composite action performs the PyPI upload. Separating the built artifact from the publisher job narrows the code that can access OIDC and ensures the published files are those tested and built earlier in the same run.

**Alternatives considered**:
- Duplicate all quality commands in both workflows: fewer files, but creates two copies of a release gate that must stay identical.
- Build and publish in one job: rejected because build tools and project-controlled scripts would share the OIDC-enabled environment.
- Use `uv publish`: technically supports Trusted Publishing, but the PyPA action is the publisher explicitly shown in PyPI's official Trusted Publishing guidance and provides PyPI publish attestations by default.

Sources: [PyPI publishing with a Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/), [PyPI Trusted Publisher security model](https://docs.pypi.org/trusted-publishers/security-model/), [PyPA action guidance](https://github.com/marketplace/actions/pypi-publish).

### 3. Require the protected GitHub `pypi` environment and bind it in PyPI

**Decision**: Require the `publish` job to reference GitHub environment `pypi`. Register a PyPI GitHub Trusted Publisher with owner `PINTOS-LTDA`, repository `python-utils`, workflow file `release.yml`, and environment `pypi`. Require approval from designated maintainers and restrict eligible release refs where supported.

**Rationale**: PyPI recommends environment binding; GitHub environment rules can require a reviewer before the job starts. The identical environment name must be used in the workflow and PyPI publisher configuration. GitHub documents a plan/visibility limitation: required reviewers on Free/Pro/Team are available only for public repositories. Since this project has private-Git installation guidance, maintainers must confirm plan support for the actual repository visibility before rollout. If unsupported, upgrading the plan is required to retain the already-approved FR-005 behavior.

**Alternatives considered**:
- Register without an environment: rejected because it loses the approval and additional identity binding required by the spec.
- Remove reviewer approval if the GitHub plan disallows it: rejected because it would violate an approved functional requirement.

Sources: [PyPI publisher setup](https://docs.pypi.org/trusted-publishers/adding-a-publisher/), [GitHub deployment environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments).

### 4. Limit permissions and pin workflow actions

**Decision**: Declare read-only repository permissions for validation/build jobs. Grant `id-token: write` only to the isolated `publish` job; do not configure username, password, secret, or API-token fallback. Pin every third-party action to a full commit SHA and include a human-readable version comment.

**Rationale**: Trusted Publishing exchanges a GitHub OIDC identity for a short-lived PyPI credential. The job-level permission limits where that identity can be requested. GitHub documents full SHA pinning as the immutable action reference; tags can move.

**Alternatives considered**:
- Grant workflow-level `id-token: write`: rejected because every job in the workflow would have access to the permission.
- Reference moving action tags such as `@v1`: rejected for the production publisher despite being shown in simple examples; immutable pinning is appropriate for the release security boundary.
- Store a PyPI API token: rejected by FR-007 and unnecessary with Trusted Publishing.

Sources: [PyPI Trusted Publisher use](https://docs.pypi.org/trusted-publishers/using-a-publisher/), [GitHub secure use guidance](https://docs.github.com/en/actions/reference/security/secure-use).

### 5. Keep project version static and validate the tag before building

**Decision**: Retain `[project].version` in `pyproject.toml` as the version source. Require a stable tag in the exact form `vMAJOR.MINOR.PATCH`, strip the leading `v`, and compare exact normalized strings before running release build/publish. Query the version-specific endpoint before every upload: an existing version or inconclusive network/API result fails closed for maintainer review. A project-level JSON response, including 404, does not prove name availability or ownership. For the first release, configure the exact pending publisher and review name eligibility through PyPI; PyPI's first-use project creation and publisher authentication are authoritative, and rejection must stop before upload.

**Rationale**: The project already declares a static version. A direct comparison is visible and deterministic, and introduces no VCS version plugin or dependency. PyPI's release-specific JSON endpoint supports the duplicate-version preflight; PyPI remains authoritative and rejects duplicate uploads. A project-name 404 cannot establish name availability, and a pending publisher does not reserve the name. Network/API errors must not be treated as proof that a version is unused.

**Alternatives considered**:
- `hatch-vcs` dynamic versions: rejected because it would add a build plugin and move version authority from the already-static project metadata into VCS state.
- Accept pre-release tags: rejected because the approved scope explicitly limits v1 to stable releases and Python package versions follow PEP 440 details that need a separately approved tag mapping.

Sources: [GitHub release event context](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), [PyPI JSON API](https://docs.pypi.org/api/json/), [PyPI project name selection](https://docs.pypi.org/project-management/choosing-a-name/), [creating a PyPI project with a pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/), [uv package build](https://docs.astral.sh/uv/concepts/projects/build/).

### 6. Build both distributions through uv from the tagged checkout

**Decision**: After validation and quality checks, run `uv build --no-sources`, preserve the resulting wheel and sdist as a GitHub Actions artifact, and transfer those exact files to the publisher job. Verify that both filenames and embedded metadata agree on package name, version, and approved license.

**Rationale**: uv builds both source and binary distributions by default. Its publishing guide recommends `--no-sources` so package builds do not depend on uv-only source overrides. The package is pure Python, so it needs one universal wheel rather than a platform wheel matrix. Build once and transfer the artifact to avoid accidentally publishing a different rebuild.

**Alternatives considered**:
- Build only the wheel: rejected because FR-004 requires both wheel and sdist.
- Rebuild within the publishing job: rejected because the publish job should contain only artifact retrieval and upload.
- Introduce a separate build backend or cibuildwheel: rejected because the current Hatchling configuration and pure-Python package do not need them.

Sources: [uv building and publishing](https://docs.astral.sh/uv/guides/package/), [uv build behavior](https://docs.astral.sh/uv/concepts/projects/build/), [PyPA packaging flow](https://packaging.python.org/en/latest/flow/).

### 7. Declare the approved MIT license using PEP 639

**Decision**: Use `license = "MIT"` with `license-files = ["LICENSE"]` in `[project]`, and include the complete MIT license text in the repository and both distributions. Keep the holder/year as a release readiness input for the authorized rights holder.

**Rationale**: The current PyPA metadata standard defines the SPDX expression and license-file fields. Hatchling 1.27 supports PEP 639, and the current `pyproject.toml` already requires Hatchling >=1.27. This aligns package metadata with the feature's approved MIT choice without inventing the copyright holder.

**Alternatives considered**:
- Old `license = {file = "LICENSE"}` form: rejected because PEP 639 supersedes that table form.
- `License ::` classifier as the license declaration: rejected because the classifier is deprecated for license identification in Core Metadata 2.4.
- Placeholder rights-holder text: rejected because the spec requires accurate license terms.

Sources: [PyPA project metadata guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/), [PEP 639](https://peps.python.org/pep-0639/).

### 8. Use PyPI publish attestations and verify every uploaded file

**Decision**: Keep the PyPA action's publish attestations enabled for both files. After publication, verify each file's provenance against the expected repository, source revision, and `release.yml` publisher identity. Do not add GitHub SLSA build provenance in this feature.

**Rationale**: PyPI publish attestations are the provenance type produced for Trusted Publishing and are generated by default by the canonical PyPA workflow. The PyPI Integrity API provides per-file provenance. Adding separate build provenance would require another attestation process and permissions not needed by this specification. PyPI uploads one file at a time, so post-upload failure can leave a partial release; operator docs must tell maintainers to inspect PyPI before retrying.

**Alternatives considered**:
- Disable attestations: rejected because every distribution must have provenance.
- Add GitHub/SLSA build provenance: deferred; the spec needs publisher/repository/source evidence, while broadening build permissions would require separate security design.
- Blindly rerun an upload after error: rejected because a partial upload can already exist and PyPI versions/files cannot be replaced.

Sources: [PyPI provenance](https://docs.pypi.org/using-pypi/package-security/provenance/), [PyPI Integrity API](https://docs.pypi.org/api/integrity/), [PyPI upload behavior](https://docs.pypi.org/api/upload/), [PyPA action](https://github.com/marketplace/actions/pypi-publish).

## External Configuration to Capture in the Release Guide

- PyPI package/distribution name: `pintos-utils`.
- GitHub owner/repository: `PINTOS-LTDA` / `python-utils`.
- Trusted workflow path: `.github/workflows/release.yml` (PyPI stores the filename `release.yml`).
- GitHub environment and PyPI publisher environment claim: `pypi`.
- Required GitHub environment reviewer(s): designated project maintainers; confirm feature availability for the repository's visibility and plan.
- Stable tag format: `vMAJOR.MINOR.PATCH`; no prerelease tags in this release path.
- License holder/year: supplied by the authorized rights holder before the first release.

No unresolved design clarification remains. The reviewer-plan check and license holder/year are explicit operational preconditions, not reasons to weaken the approved specification.
