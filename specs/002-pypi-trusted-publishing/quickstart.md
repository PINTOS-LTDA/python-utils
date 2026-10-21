# Release Readiness and Operator Quickstart

This guide records the initial PyPI publication and documents release readiness and verification for future releases. It does not publish from a local machine.

## Prerequisites

- Python 3.11 or later and uv installed.
- Repository checks green on the proposed source revision.
- Accurate MIT `LICENSE` text with the rights-holder name and year.
- GitHub Trusted Publisher configured for `PINTOS-LTDA/python-utils`, workflow `release.yml`, and environment `pypi`.
- The GitHub `pypi` environment was created first and has the designated required reviewer(s), and the current repository visibility/account plan supports this protection rule. GitHub can automatically create a referenced environment without protection rules, so verify this environment in repository settings before configuring PyPI.
- PyPI project `pintos-utils` exists, and its Trusted Publisher is active for owner `PINTOS-LTDA`, repository `python-utils`, workflow `release.yml`, and environment `pypi`.
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

External setup review on 2026-10-21:

- GitHub environment `pypi` exists and requires approval from `ivaneyvieira`. Its deploy-ref rule is `v*`, which includes the controlled tag `v1.0.0`. Self-review prevention and administrator bypass are disabled; no environment secret or variable is configured.
- Active GitHub ruleset `Protect v* release tags` targets `v*`, with `ivaneyvieira` as the `Always allow` bypass actor and creation, update, deletion, and force-push restrictions enabled. The ruleset covers the controlled tag `v1.0.0`.
- PyPI Trusted Publisher registration initially succeeded as a pending publisher for project `pintos-utils`, owner `PINTOS-LTDA`, repository `python-utils`, workflow `release.yml`, and environment `pypi`. After the first authorized upload, the project and publisher are active with that identity.
- Static workflow audit passed: only the isolated `publish` job has `id-token: write`; no static PyPI credential was found; all third-party actions are pinned to full commit SHAs. The active publisher's owner/repository/workflow/environment match the `publish` job configuration.

### Controlled no-upload test record (2026-10-21, attempt 1)

- Published the controlled, non-prerelease GitHub Release `v1.0.0` from `main` at commit `16751205d9b5c2c7d52093bdfb36174e6dc88a61`. The release is a public GitHub release used to exercise the protected deployment gate; it is not a PyPI publication and remains available at [the GitHub release page](https://github.com/PINTOS-LTDA/python-utils/releases/tag/v1.0.0).
- Workflow [run 39645065866, attempt 1](https://github.com/PINTOS-LTDA/python-utils/actions/runs/39645065866/attempts/1) passed stable-tag validation and the tagged-revision test/lint/type-check/build job. The `pypi` deployment was rejected by `ivaneyvieira`; because the environment protects the entire `publish` job, the job ended before its download and PyPI upload steps ran.
- PyPI account verification after rejection showed no project or active publisher yet, and the `pintos-utils` publisher was still pending. This confirmed attempt 1 did not create the project or upload distributions. Its `distributions` artifact (24.3 KB; GitHub artifact digest `sha256:063beb4fae26e99d16b3618c2bb77587206474ef8911508c5a668f65afd46d87`) is retained by GitHub Actions and is not evidence of a PyPI upload or provenance.
- The first attempt was intentionally rejected and performed no production deployment. Attempt 2 was subsequently approved and published; its release evidence and consumer checks are recorded below.

### Authorized publication and consumer validation (2026-10-21)

- GitHub [run 39645065866, attempt 2](https://github.com/PINTOS-LTDA/python-utils/actions/runs/39645065866/attempts/2) succeeded for release `v1.0.0`, source commit `16751205d9b5c2c7d52093bdfb36174e6dc88a61`. Stable-tag validation, the tagged-revision quality/build job, and `Publish distributions to PyPI` all passed. The deployment protection record shows `ivaneyvieira` approved the `pypi` environment.
- PyPI now serves [pintos-utils 1.0.0](https://pypi.org/project/pintos-utils/1.0.0/) with both release files. The project page renders the README. Metadata in both downloaded distributions reports name `pintos-utils`, version `1.0.0`, `Requires-Python: >=3.11`, `Provides-Extra: gmail`, source `https://github.com/PINTOS-LTDA/python-utils`, and `License-Expression: MIT`. The Gmail extra declares `google-api-python-client>=2.150,<3`, `google-auth>=2.35,<3`, and `google-auth-httplib2>=0.2,<1`.
- The sdist is 16,880 bytes with SHA-256 `df6bba0052d54e7f218b736dacc9ed2a40a852da78367ce645c0ad4ba74b448e`; it contains `pintos_utils-1.0.0/LICENSE`. The wheel is 9,028 bytes with SHA-256 `56b404c038754adc5a56d5ceecc2b8ed8443cb308d0e75309fbf29324b1c33bb`; it contains `pintos_utils-1.0.0.dist-info/licenses/LICENSE`.
- Consumer installs were checked in separate clean virtual environments using CPython 3.14.8:

  ```bash
  /usr/bin/python -m venv /tmp/pintos-utils-base-venv
  uv pip install --python /tmp/pintos-utils-base-venv/bin/python "pintos-utils==1.0.0"
  /tmp/pintos-utils-base-venv/bin/python -c 'import pintos_utils; from pintos_utils.email import EmailMessage'

  /usr/bin/python -m venv /tmp/pintos-utils-gmail-venv
  uv pip install --python /tmp/pintos-utils-gmail-venv/bin/python "pintos-utils[gmail]==1.0.0"
  /tmp/pintos-utils-gmail-venv/bin/python -c 'import google.auth, googleapiclient.discovery, google_auth_httplib2; from pintos_utils.email import EmailMessage; from pintos_utils.email.providers.gmail import GmailEmailSender'
  ```

  Both installs and imports passed. The base environment has no Gmail dependencies; importing `GmailEmailSender` there raises the documented `ImportError` directing consumers to install the `gmail` extra. The Gmail environment imports the provider and its Google dependencies successfully.
- PyPI's per-file provenance panels report that it verified the sdist and wheel at the SHA-256 values above. For both files they identify GitHub Actions, repository `PINTOS-LTDA/python-utils`, commit `16751205d9b5c2c7d52093bdfb36174e6dc88a61`, workflow `.github/workflows/release.yml`, and publishing run `39645065866/attempts/2`. The corresponding [sdist](https://search.sigstore.dev/?logIndex=3359952788) and [wheel](https://search.sigstore.dev/?logIndex=3359952983) Sigstore transparency entries identify `refs/tags/v1.0.0`, the same source/build digest, and the GitHub Actions `pypi` environment. The GitHub run records approval of that environment. The `pypi-attestations verify pypi --repository https://github.com/PINTOS-LTDA/python-utils <artifact-url>` command returned `OK` for the wheel. Its sdist request returned HTTP 503 from PyPI's Integrity API on two attempts; PyPI's per-file attestation panel and the transparency entry were checked separately and show the expected digest and identity. Retry the CLI check if a local cryptographic re-verification of the sdist is needed after that endpoint recovers.

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

## Trusted Publisher Review and No-upload Approval Check

The initial review compared the PyPI publisher with the OIDC claims of the isolated `publish` job in `release.yml`: owner `PINTOS-LTDA`, repository `python-utils`, workflow `release.yml`, and environment `pypi`. The publisher and workflow identities matched. For future publisher or workflow changes, repeat this review, confirm that no unapproved publisher is configured, and inspect all workflows to ensure only the isolated `publish` job has `id-token: write` and no static PyPI credential is present. Any mismatch blocks release readiness. Do not invoke the publishing action with a different project or distribution to test identity rejection.

The initial no-upload approval check rejected attempt 1 at the protected `pypi` environment and confirmed that no distribution was uploaded. Attempt 2 was separately approved and its production publication was verified above.

## First-Time Repository Setup

1. Confirm the canonical source URL is `https://github.com/PINTOS-LTDA/python-utils` and review the intended PyPI name `pintos-utils` against PyPI's name guidance. Do not treat a project JSON 404 as proof that the name is available.
2. In GitHub repository settings, create environment `pypi`, require approval from designated maintainers, and restrict deployable refs to stable version tags where supported. Confirm required-reviewer support for this repository's visibility and account plan. Create and verify this protection before configuring PyPI; a workflow reference can create a missing environment without protection rules.
3. Add a repository ruleset that limits creation and modification of `v*` release tags to authorized maintainers.
4. For a new package, after verifying the protected environment exists, configure a pending GitHub Trusted Publisher in PyPI for the exact project name, repository, workflow, and environment. A pending publisher does not reserve the name; PyPI may reject first-use project creation if the name is unavailable or was registered in the meantime. This repository's first-use setup succeeded and its publisher is active, as recorded above.
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
