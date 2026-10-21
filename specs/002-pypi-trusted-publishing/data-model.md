# Release Data Model

This feature adds no persistent application data. The entities below describe the release protocol, transient workflow state, and external PyPI records.

## Entities

### Release

One approved stable project version, associated with one GitHub release tag and one immutable source revision.

| Field | Type | Rules |
|---|---|---|
| `package_name` | string | Exactly `pintos-utils`. |
| `version` | string | Static `[project].version`; normalized stable `MAJOR.MINOR.PATCH`. |
| `tag` | string | Exactly `v` followed by `version`; prerelease suffixes are not accepted. |
| `source_revision` | Git commit SHA | The commit identified by the published GitHub release tag. |
| `validation_status` | status | Must pass tag, version, duplicate-version, quality, and build gates before approval. |
| `approval_status` | status | `pending`, `approved`, or `rejected` by the protected `pypi` environment. |
| `publication_status` | status | `not_started`, `in_progress`, `complete`, `failed`, or `partial`. |

**State progression**: `proposed -> validated -> built -> awaiting_approval -> publishing -> complete`. Validation, quality, or build failure and approval rejection stop before upload. An upload error is `failed` or `partial` depending on what PyPI already accepted; it requires inspection before a retry.

### Distribution

One immutable artifact produced for a Release.

| Field | Type | Rules |
|---|---|---|
| `filename` | string | One wheel (`.whl`) and one source archive (`.tar.gz`) are required. |
| `package_name` | string | Must match `pintos-utils` after Python distribution-name normalization. |
| `version` | string | Must equal the parent Release version. |
| `sha256` | hexadecimal digest | Computed from the built file and used to identify that exact artifact. |
| `license_expression` | SPDX expression | `MIT`. |
| `license_file` | path | `LICENSE` is included in the archive and metadata. |
| `provenance_status` | status | `pending`, `present`, or `verified` for the uploaded file. |

### Trusted Publisher

An external PyPI/GitHub configuration binding an OIDC identity to the publication job.

| Field | Value/Rule |
|---|---|
| `provider` | GitHub Actions OIDC |
| `owner` | `PINTOS-LTDA` |
| `repository` | `python-utils` |
| `workflow_file` | `release.yml` |
| `environment` | `pypi` |
| `credential` | Short-lived OIDC exchange; no persisted PyPI API token |

The configured values must match the workflow run's identity. Any mismatch fails publication closed.

### Release Provenance

PyPI's attestation record for one Distribution, identifying the published file digest and its authorized publishing identity. Verification checks each wheel and sdist independently against the expected repository, source revision, and release workflow. It is a per-file record; checking only the release page or one file does not satisfy the release criterion.

## Relationships

- One Release has exactly two required Distributions: one wheel and one sdist.
- Each Distribution belongs to exactly one Release and has its own digest and provenance record.
- One Trusted Publisher authorizes the `publish` job for the Release workflow.
- A Release may have a partial publication state if PyPI accepts one distribution before a later upload fails.

## Validation Rules

1. A release tag must match `vMAJOR.MINOR.PATCH`; stripping `v` must equal the package metadata version exactly.
2. The version-specific preflight checks whether the version already exists; a 404 means only that the queried version was not found. A project-level JSON 404 does not prove that a name is available or owned by the intended maintainer. For a first release, the operator configures the pending publisher and reviews name eligibility through PyPI. Rejection of project creation or publisher authentication blocks upload; network/API uncertainty also blocks the attempt.
3. The quality workflow and build must succeed for the tagged source revision.
4. Exactly one expected wheel and one sdist must be present, with matching normalized name, version, and MIT license metadata/file.
5. The publishing job cannot start until the GitHub `pypi` environment approves it.
6. OIDC permission is scoped to the isolated publishing job, and PyPI must match the registered owner, repository, workflow, and environment.
7. A completed release requires PyPI publish provenance on both files. Any post-upload ambiguity is reported as incomplete and inspected before retry.
