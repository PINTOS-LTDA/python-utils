# Tasks: PyPI Release Automation

**Input**: Design documents from `specs/002-pypi-trusted-publishing/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Organization**: Tasks are grouped by the three approved user stories. The release workflow and Trusted Publisher setup are related: the workflow can be validated without uploading, while the first authorized PyPI upload requires both P1 stories to be complete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Work can run in parallel because it affects separate files or independent external settings and has no unfinished dependency.
- **[Story]**: User story label from `spec.md`.
- Every task includes its target file path. External GitHub/PyPI configuration tasks reference the repository runbook that must document the settings.

## Phase 1: Setup (Shared Project and CI Infrastructure)

**Purpose**: Prepare the approved package metadata and shared GitHub Actions checks.

- [X] T001 [P] Add the complete MIT text with the authorized copyright holder and year in `LICENSE`; do not use placeholder ownership text.
- [X] T002 [P] Create reusable workflow `.github/workflows/_quality.yml` with `workflow_call`, Python 3.11, locked uv development sync, pytest/coverage, Ruff lint/format, and mypy; use checkout/setup actions pinned to reviewed full commit SHAs, run `uv build --no-sources`, and grant read-only repository access with no OIDC permission.
- [X] T003 [P] Update `pyproject.toml` with PEP 639 `license = "MIT"`, `license-files = ["LICENSE"]`, the canonical source URL, and the `LICENSE` sdist inclusion while preserving the current version, Python minimum, and Gmail extra (depends on T001).
- [X] T004 [P] Create `.github/workflows/ci.yml` for pull requests and branch pushes; call `_quality.yml` with distribution artifact upload disabled and no publishing identity (depends on T002).

## Phase 2: Foundational (Release Readiness Gates)

**Purpose**: Verify shared build contents and record external release prerequisites before story-specific publishing work.

- [X] T005 [P] Create `docs/releases.md` with the verified repository identity (`PINTOS-LTDA/python-utils`), PyPI name (`pintos-utils`), workflow filename (`release.yml`), environment (`pypi`), stable tag format, and explicit checks for reviewer-plan support, PyPI name guidance and pending-publisher limits, and the supplied MIT holder/year; state that a project JSON 404 does not prove name availability.
- [X] T006 [P] Extend `.github/workflows/_quality.yml` to verify that the build contains exactly one expected wheel and one sdist with matching name/version, Python requirement, Gmail extra, MIT license metadata, and included license file; add a `workflow_call` option that uploads `dist/` only for a release run using a full-SHA-pinned artifact action.

**Checkpoint**: CI can run shared gates without OIDC, and the release build can validate both artifacts after the approved license metadata is present.

## Phase 3: User Story 1 - Publish an approved library release (Priority: P1) 🎯 MVP

**Goal**: A matching stable GitHub release passes the project gates and produces the exact tagged wheel and sdist for the protected PyPI publication job.

**Independent Test**: Process a controlled release candidate. Confirm prerelease, malformed tag, version mismatch, existing version, inconclusive version lookup, failed quality gate, and build failure stop before publication. Treat name eligibility as an external PyPI setup concern: a project JSON 404 is not evidence of availability. Review the first-use project-creation and publisher-authentication failure path to confirm rejection stops before the file-upload action without a credential fallback. A matching tag builds the wheel and sdist from its tagged commit and reaches the protected publication gate. PR/branch runs never call the publisher. The first real upload is verified after US2 configures the trusted identity.

- [X] T007 [US1] Create `.github/workflows/release.yml` for `release: published`, reject prereleases and tags outside stable `vMAJOR.MINOR.PATCH`, use the release event's tagged revision, serialize runs by release tag, set explicit least-privilege default permissions, and pin its checkout action to a reviewed full commit SHA.
- [X] T008 [P] [US1] Expand `specs/002-pypi-trusted-publishing/quickstart.md` with no-upload validation scenarios for prerelease/malformed tags, tag/version mismatch, existing version, inconclusive version lookup, failed quality gate, and artifact inspection; document the offline mocked-response tests, that project-name eligibility is external, and that a project JSON 404 is not proof of availability.
- [X] T009 [US1] Add typed helper `scripts/release_preflight.py` and offline tests in `tests/unit/test_release_preflight.py`; compare the tag without its leading `v` to `[project].version`, query only the version-specific PyPI endpoint for an existing release, and cover existing, absent, and inconclusive responses with mocked HTTP. Wire the helper into `.github/workflows/release.yml` before build/publication and extend `.github/workflows/_quality.yml` mypy coverage to include the helper; do not infer name availability from a project JSON 404 and fail closed with distinct validation/version/registry errors (depends on T007).
- [X] T010 [US1] Call `.github/workflows/_quality.yml` from `.github/workflows/release.yml` for the exact tag revision, enable artifact upload only on the release call, and make its success a prerequisite of publication (depends on T009).
- [X] T011 [US1] Add the `publish` job in `.github/workflows/release.yml` after successful validation/build; bind it to environment `pypi`, scope `id-token: write` to this job only, download the built artifact, and invoke `pypa/gh-action-pypi-publish` once with attestations enabled. Pin download/publish actions to reviewed full commit SHAs; add no API token or fallback (depends on T010).

**Checkpoint**: Invalid releases fail before upload; a matching release produces only the tested tag artifact and stops at the protected environment until approval.

## Phase 4: User Story 2 - Authorize publication without a stored PyPI token (Priority: P1)

**Goal**: PyPI trusts only the intended release workflow and environment, and GitHub approval gates the job without a long-lived token.

**Independent Test**: Compare the PyPI publisher's owner/repository/workflow/environment with the actual OIDC-bound publish job. Verify the protected environment has designated reviewers, reject a controlled deployment and confirm no files were uploaded, and inspect all workflows for a static PyPI token or OIDC permission outside `publish`.

- [X] T012 [US2] Complete `docs/releases.md` with the pending/normal Trusted Publisher setup, exact field values, GitHub environment reviewer setup, eligible tag restrictions, action pin review, and approval/rejection procedure.
- [ ] T013 [P] [US2] Configure the PyPI project or pending publisher using `pintos-utils`, owner `PINTOS-LTDA`, repository `python-utils`, workflow `release.yml`, and environment `pypi`; follow PyPI's name guidance, record that a pending publisher does not reserve the name, and stop for owner review on project-creation or publisher rejection without renaming automatically (follow `docs/releases.md`).
- [ ] T014 [P] [US2] Configure GitHub environment `pypi` with designated required reviewer(s), eligible stable release refs, and the repository tag ruleset; verify the current account plan supports required reviewers for this repository's visibility (follow `docs/releases.md`).
- [ ] T015 [US2] Audit `.github/workflows/ci.yml`, `.github/workflows/_quality.yml`, and `.github/workflows/release.yml` to confirm only the isolated `publish` job has `id-token: write` and no static PyPI credential exists. Compare the effective PyPI Trusted Publisher configuration for `pintos-utils` with the `publish` job claims (owner, repository, workflow filename, and environment) and confirm no other publisher is configured. Reject a controlled deployment through the protected environment and confirm no files were uploaded. Do not attempt a mismatched PyPI publication or use an alternate project/distribution as a probe. Record the review and no-upload result in `specs/002-pypi-trusted-publishing/quickstart.md` (depends on T013 and T014).

**Checkpoint**: A reviewer can approve or reject the protected job; only a matching PyPI/GitHub identity can enter the upload action.

## Phase 5: User Story 3 - Install and inspect a published release (Priority: P2)

**Goal**: Consumers can install the base library or Gmail extra from PyPI and inspect accurate metadata and provenance.

**Independent Test**: After an authorized release, install the exact version in clean supported environments with and without `[gmail]`; verify imports, package metadata/license, and provenance for both distribution files.

- [X] T016 [P] [US3] Update `README.md` with PyPI installation commands for `pintos-utils` and `pintos-utils[gmail]`, preserving local, editable, and private Git installation instructions.
- [X] T017 [P] [US3] Update `docs/email.md` with the PyPI base/extra installation examples and retain the provider usage and OAuth documentation.
- [ ] T018 [US3] Inspect the PyPI project page and release metadata against `specs/002-pypi-trusted-publishing/contracts/distribution.md`; confirm name, version, README, Python minimum, Gmail extra, source URL, MIT expression, and license file, and record results or blockers in `specs/002-pypi-trusted-publishing/quickstart.md`.
- [ ] T019 [US3] Install the released base package and `gmail` extra in separate clean environments, verify the documented imports and optional dependency behavior, and record commands/results in `specs/002-pypi-trusted-publishing/quickstart.md`.
- [ ] T020 [US3] Verify the PyPI provenance for the wheel and sdist independently against the expected digest, source repository, release revision, workflow, and environment; record the outcome in `specs/002-pypi-trusted-publishing/quickstart.md`.

**Checkpoint**: Both consumer installation paths work, metadata reflects the approved package, and each released file has matching verifiable provenance.

## Phase 6: Polish and Cross-Cutting Validation

**Purpose**: Complete operational recovery guidance and verify the implemented feature against its approved acceptance criteria.

- [X] T021 Finalize `docs/releases.md` with the failure categories from FR-013, partial-upload handling, checks before retry, and a clear instruction never to retry an ambiguous upload blindly.
- [X] T022 Run the local non-publishing validation steps in `specs/002-pypi-trusted-publishing/quickstart.md`, including offline mocked-response tests for the release-version preflight, and review the release workflow against FR-001–FR-013 and SC-001–SC-005 without performing an unapproved production upload.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Starts immediately. T001 and T002 can run in parallel; T003 follows T001 and T004 follows T002. T003 and T004 can then run in parallel.
- **Foundational (Phase 2)**: Starts after Setup. T005 (runbook identity/prerequisites) and T006 (artifact validation) can run in parallel; both must finish before release-specific workflow work.
- **User Story 1 (Phase 3)**: Depends on Setup and Foundational. T007 and T008 can run in parallel; T009–T011 are sequential because they refine the same release workflow and its job dependencies.
- **User Story 2 (Phase 4)**: Depends on the release workflow from US1. T013 and T014 are independent external settings after T012 documents the exact values; T015 audits the combined configuration.
- **User Story 3 (Phase 5)**: T016 and T017 are independent documentation tasks. PyPI inspection, clean installs, and provenance verification (T018–T020) require the first authorized release, so they depend operationally on US1 and US2.
- **Polish (Phase 6)**: Depends on all required stories. The final validation must not trigger an unapproved production upload.

### User Story Dependencies

- **US1 (P1)**: Depends on shared CI/build and package metadata. It can validate all pre-upload gates independently; an authorized PyPI upload requires the US2 publisher and environment configuration.
- **US2 (P1)**: Depends on the `release.yml` publisher job from US1 so the exact workflow identity can be registered. No separate long-lived credentials are introduced.
- **US3 (P2)**: Installation documentation can be written after setup; its PyPI installation and provenance acceptance checks depend on a successful US1+US2 release.

### Dependency Graph

```text
T001 -> T003 ─┐
              ├-> T005 + T006 -> T007 -> T009 -> T010 -> T011
T002 -> T004 ─┘                  ^
                                 └── T008 runs in parallel with T007
                                                       |
                                                       v
                                      T012 -> (T013 + T014) -> T015
                                                       |
                         (T016 + T017) -----------------+
                                                       v
                                             T018 -> T019 -> T020
                                                       v
                                                 T021 -> T022
```

### Parallel Opportunities

- Setup: T001 with T002; then T003 with T004.
- Foundational: T005 with T006.
- US1: T007 with T008 (workflow and separate validation guide).
- US2 external setup: T013 with T014 after T012.
- US3 documentation: T016 with T017.

## Parallel Examples

### Setup

```text
Task: T001 Add the authorized MIT license text in LICENSE
Task: T002 Create the reusable CI workflow in .github/workflows/_quality.yml
```

After those complete:

```text
Task: T003 Update PEP 639/package metadata in pyproject.toml
Task: T004 Add the PR/branch workflow in .github/workflows/ci.yml
```

### User Story 1

```text
Task: T007 Create the release trigger and tagged workflow in .github/workflows/release.yml
Task: T008 Add safe non-publishing release validation scenarios in specs/002-pypi-trusted-publishing/quickstart.md
```

### User Story 2 Configuration

```text
Task: T013 Configure the exact PyPI Trusted Publisher from docs/releases.md
Task: T014 Configure the protected GitHub pypi environment and tag restrictions from docs/releases.md
```

### User Story 3 Documentation

```text
Task: T016 Update PyPI installation instructions in README.md
Task: T017 Update provider-specific installation instructions in docs/email.md
```

## Implementation Strategy

### MVP

The smallest production-capable increment is US1 plus the required US2 identity/environment setup. Before the first upload, also complete US3's consumer installation documentation (T016–T017) and the approved package/license metadata (T001, T003), as required by FR-010 and FR-011. Do not treat a build artifact waiting for approval as a completed PyPI release.

### Incremental Delivery

1. Complete Setup and Foundational phases; branch/PR CI remains non-publishing.
2. Implement US1 and validate version failures, quality/build gates, artifact contents, and the protected-job boundary without uploading.
3. Configure US2's PyPI publisher and GitHub environment; validate approval/rejection and identity restrictions.
4. Complete consumer installation documentation before the first authorized production release.
5. After an authorized release, complete US3's clean-install, metadata, and per-file provenance checks.
6. Complete the recovery runbook and final acceptance review.

## Notes

- [P] means separate files or external settings can be worked on without an unfinished dependency.
- User story labels map directly to the approved scenarios in `spec.md`.
- The project/version/license metadata, PyPI publisher, and GitHub environment must all match; do not infer the rights-holder name/year or substitute a different package name.
- A first public upload is an operator-controlled production action. Task completion must not perform it without an explicit release instruction and approval.
