# Release Readiness and Operator Quickstart

This guide validates release readiness and describes the first controlled PyPI release. It does not publish from a local machine.

## Prerequisites

- Python 3.11 or later and uv installed.
- Repository checks green on the proposed source revision.
- Accurate MIT `LICENSE` text with the rights-holder name and year.
- GitHub Trusted Publisher configured for `PINTOS-LTDA/python-utils`, workflow `release.yml`, and environment `pypi`.
- The GitHub `pypi` environment was created first and has the designated required reviewer(s), and the current repository visibility/account plan supports this protection rule. GitHub can automatically create a referenced environment without protection rules, so verify this environment in repository settings before configuring PyPI.
- PyPI pending publisher configured for the exact project name `pintos-utils`; the name remains unreserved until successful first use.
- Stable release tag `vMAJOR.MINOR.PATCH` matches `[project].version` exactly after removing `v`.

For a new project, PyPI's pending publisher can create the project on first authorized upload, but it does not reserve the package name before then. A project JSON 404 does not prove name availability. Follow PyPI's name guidance when configuring the pending publisher, and treat PyPI's first-use project creation and publisher authentication as authoritative. A rejection must stop before any distribution is uploaded.

## Local Validation (No Network Publishing)

Run from the repository root:

```bash
uv sync --locked --group dev --extra gmail
uv run pytest --cov=pintos_utils --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy src scripts/release_preflight.py
uv run pytest tests/unit/test_release_preflight.py
uv build --no-sources
```

Expected result: all checks pass, and `dist/` contains one `pintos_utils-<version>-py3-none-any.whl` plus one `pintos_utils-<version>.tar.gz`. Inspect both distributions to confirm that package name, version, Python requirement, Gmail extra, MIT license metadata, and license file agree. If either archive is missing or inconsistent, stop before tagging.

The workflow's shared non-publishing job runs the same gates and builds from the release tag. A local build does not authorize or upload to PyPI.

## Local Validation Record (2026-10-21)

Latest local non-publishing validation used Python 3.11.17 and the locked development/Gmail dependencies:

- `uv sync --locked --group dev --extra gmail`: passed in a temporary environment.
- `uv run pytest --cov=pintos_utils --cov-report=term-missing`: 55 tests passed; package coverage was 86%.
- `uv run ruff check .` and `uv run ruff format --check .`: passed.
- `uv run mypy src scripts/release_preflight.py`: passed.
- `uv build --no-sources`: wheel and sdist built successfully; the workflow's metadata/license verifier passed for both distributions.
- All three workflow YAML files parsed successfully; the release tag shell check passed `bash -n` and rejected a leading-zero tag.

Read-only configuration check on 2026-10-21: GitHub repository settings reported no existing environments. No PyPI Trusted Publisher settings were changed or verified. The protected `pypi` environment, required reviewer identities, tag ruleset, and PyPI publisher still need repository-owner configuration and review before an authorized release.

The release-preflight unit tests use mocked HTTP responses and make no network requests. They verify that an existing version blocks release, a version-specific 404 means only that the queried version was not found, and network/API failures stop the preflight. They do not claim to verify project-name availability or PyPI ownership.

### Release gate scenarios (no upload)

Check the release workflow with controlled release candidates or mocked inputs and confirm that each case stops before the `publish` job:

- prerelease GitHub release;
- malformed or non-stable tag, including a version with leading zeroes;
- release tag whose version differs from `[project].version`;
- version-specific PyPI endpoint reports that the version already exists;
- version lookup returns a network/API error or any inconclusive response;
- quality gate or distribution build fails.

A matching stable tag should build exactly one wheel and one sdist from its tagged source revision. Inspect both files using the distribution checks in the shared quality workflow. These scenarios do not upload files. Name eligibility is an external PyPI setup concern: a project JSON `404` is not proof that the name is available, and a pending publisher does not reserve it.

## Trusted Publisher Review (No Upload)

Before production publication, inspect the PyPI publishing settings for `pintos-utils` and compare the complete Trusted Publisher record with the OIDC claims of the isolated `publish` job in `release.yml`: owner `PINTOS-LTDA`, repository `python-utils`, workflow `release.yml`, and environment `pypi`. Confirm that no other publisher is configured for the project. Inspect all workflows to confirm that only the isolated `publish` job has `id-token: write` and that no static PyPI credential is present. Any mismatch or additional publisher blocks release readiness. Do not invoke the publishing action with a different project or distribution to test identity rejection.

For the no-upload approval check, reject a controlled deployment at the protected `pypi` environment and confirm that no distribution was uploaded. Record the publisher-configuration review and rejection result here. This check does not perform a production upload; an authorized production release is verified separately and only after explicit approval.

## First-Time Repository Setup

1. Confirm the canonical source URL is `https://github.com/PINTOS-LTDA/python-utils` and review the intended PyPI name `pintos-utils` against PyPI's name guidance. Do not treat a project JSON 404 as proof that the name is available.
2. In GitHub repository settings, create environment `pypi`, require approval from designated maintainers, and restrict deployable refs to stable version tags where supported. Confirm required-reviewer support for this repository's visibility and account plan. Create and verify this protection before configuring PyPI; a workflow reference can create a missing environment without protection rules.
3. Add a repository ruleset that limits creation and modification of `v*` release tags to authorized maintainers.
4. After verifying the protected environment exists, configure a pending GitHub Trusted Publisher in PyPI for project `pintos-utils`, owner `PINTOS-LTDA`, repository `python-utils`, workflow `release.yml`, and environment `pypi`. A pending publisher does not reserve the name; PyPI may reject first-use project creation if the name is unavailable or was registered in the meantime.
5. Confirm every third-party action in both workflow files is pinned to a verified full commit SHA and has a version comment.

## Release Procedure

1. Choose the next SemVer version and update `[project].version` before creating the tag. Ensure the license holder/year and all public package metadata are accurate.
2. Run the local gates above and review the resulting wheel and sdist contents.
3. Push a stable annotated tag `vMAJOR.MINOR.PATCH` pointing at the reviewed commit and publish a non-prerelease GitHub Release for that tag.
4. The release workflow rejects a prerelease, invalid tag, version mismatch, existing PyPI version, inconclusive version lookup, failed validation, or build failure before requesting approval. A project-level JSON 404 is not used as proof of name availability; PyPI project-creation or publisher-authentication rejection stops before file upload.
5. A designated maintainer reviews the deployment details and approves the `pypi` environment. Rejection or cancellation stops publication.
6. After the publish job completes, confirm both files appear on the PyPI release page. Verify the publish attestation for each file against the expected repository, tagged revision, workflow, and environment.
7. In a clean consumer environment, install and import the base package and separately install the Gmail extra:

```bash
python -m pip install "pintos-utils==<version>"
python -c "import pintos_utils"
python -m pip install "pintos-utils[gmail]==<version>"
```

The `pypi-attestations` CLI can verify each downloaded distribution against PyPI provenance. See [PyPI's attestation verification instructions](https://docs.pypi.org/attestations/consuming-attestations/).

## Failure Recovery

- **Tag/version or quality failure**: fix the source/version, create a new correct release tag, and rerun gates; do not bypass validation.
- **Required approval rejected**: inspect release intent and workflow results, then publish a new approved run only after the designated maintainer decision.
- **Publisher identity failure**: compare the owner, repository, workflow filename, and environment configured in PyPI with the job OIDC identity. Do not add or use a static token.
- **Project-name or pending-publisher rejection**: treat PyPI's rejection as authoritative, confirm the intended name and publisher configuration with the project owner, and verify that no distribution was accepted. Do not infer availability from a JSON 404 or change the package name automatically.
- **PyPI version already exists**: do not re-upload or change the package name automatically. Inspect the existing project/release and ask its authorized owner to resolve the namespace or version decision.
- **Upload or provenance step fails**: inspect the PyPI release files and each file's provenance first. PyPI may already have accepted one distribution. Mark the run incomplete and do not retry until the uploaded state is known; published files cannot be replaced in place.
- **Missing or mismatched provenance**: do not treat the release as complete. Compare each file's attestation with the expected package digest and Trusted Publisher identity, then follow up before another upload attempt.
