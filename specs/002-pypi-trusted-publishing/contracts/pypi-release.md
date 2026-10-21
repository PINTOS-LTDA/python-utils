# PyPI Release Workflow Contract

## Identity

| Setting | Required value |
|---|---|
| PyPI project | `pintos-utils` |
| GitHub owner | `PINTOS-LTDA` |
| GitHub repository | `python-utils` |
| Trusted workflow filename | `.github/workflows/release.yml` (`release.yml` in PyPI configuration) |
| GitHub environment | `pypi` |
| Tag format | Stable `vMAJOR.MINOR.PATCH` |
| Trigger | A published, non-prerelease GitHub Release |

The owner, repository, filename, and environment in the PyPI Trusted Publisher must match the OIDC claims from the publishing job. The designated project maintainer(s) must be configured as required reviewer(s) in the environment. Availability of required reviewers must be confirmed for the repository's GitHub visibility and plan.

## Job Inputs and Outputs

| Job | Inputs | Output/required result | OIDC |
|---|---|---|---|
| `ci` / shared quality-build | PR or branch commit | pytest/coverage, Ruff lint/format, mypy, build and distribution checks | None |
| `validate` | Published release event, tag checkout | Stable tag, exact project version, intended PyPI project identity, unused PyPI version, tagged source revision | None |
| `quality-build` | Validated tag and release call to `_quality.yml` | Successful quality gates; exactly one matching wheel and one matching sdist, transferred as one workflow artifact | None |
| `publish` | Successful prior jobs, approved `pypi` environment, downloaded artifact | Both distribution files uploaded through PyPI Trusted Publishing with publish attestations enabled | `id-token: write` at this job only |

No PR, ordinary branch, validation, or quality/build job may receive `id-token: write`. The publish job may contain only the artifact-download step and one invocation of `pypa/gh-action-pypi-publish`; it does not check out project source or rebuild distributions. The shared workflow builds in both CI and release runs, but only the release caller retains the artifact for publication.

## Validation and Failure Behavior

- Tag/version mismatch, prerelease tag, duplicate PyPI version, failed quality gate, invalid distribution contents, or inconclusive version-specific lookup: stop before upload with a clear failure category. A project-level JSON 404 is not evidence that the name is available. Rejection of first-use project creation or Trusted Publisher authentication must fail closed before any file is uploaded.
- Rejected environment approval: do not upload.
- Trusted Publisher identity mismatch: fail OIDC exchange; never attempt a token fallback.
- Upload/provenance failure: report the run as incomplete. Since PyPI accepts distribution files individually, inspect the project's release files and attestations before retrying.
- Do not log credentials, OIDC tokens, recipient-like secrets, or static publishing tokens.

## Provenance Contract

Each uploaded file must have a PyPI publish attestation tied to the expected package file digest and configured publisher identity. The operator verifies provenance for the wheel and sdist independently and confirms the source repository, tagged revision, workflow, and environment. No separate GitHub build/SLSA attestation is required by this feature.

## Distribution Contract

See [distribution.md](distribution.md) for artifact naming, Python compatibility, dependency extras, metadata, and consumer installation behavior.
