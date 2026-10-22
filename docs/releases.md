# Release Runbook

This runbook defines the checks and external settings for publishing `pintos-utils` to PyPI through GitHub Actions Trusted Publishing. The workflow does not use a stored PyPI API token.

## Verified Release Identity

| Setting | Required value |
| --- | --- |
| GitHub repository | `PINTOS-LTDA/python-utils` |
| Repository visibility checked | Public (checked 2026-10-21) |
| PyPI distribution | `pintos-utils` |
| Source URL | `https://github.com/PINTOS-LTDA/python-utils` |
| Release workflow file | `.github/workflows/release.yml` (PyPI field: `release.yml`) |
| GitHub environment and PyPI environment claim | `pypi` |
| Stable release tag | `vMAJOR.MINOR.PATCH`, without prerelease suffixes |
| License | MIT; `Ivaney Vieira de Sales`, 2026 |

## Readiness Checks

### GitHub environment approval

The repository was confirmed public on 2026-10-21. GitHub's required-reviewer availability depends on repository visibility and the plan. Confirm in repository settings that the `pypi` environment offers required reviewers before enabling release publication. GitHub documents required reviewers for public repositories on Free, Pro, and Team plans; if the setting is unavailable, stop and resolve account-plan support rather than removing the approval gate. Select the required reviewer(s) from authorized project maintainers; this runbook does not invent reviewer identities.

Configure the `pypi` environment to require approval from `ivaneyvieira`, restrict deployment to the intended stable release tags when supported, and reject a controlled deployment during the no-upload check. This is the sole reviewer identity supplied so far; leave GitHub's optional self-review prevention disabled unless another reviewer is added, or the only reviewer could be unable to approve a release they initiate.

Create and protect the `pypi` environment before configuring PyPI's pending publisher. GitHub automatically creates a missing environment when a workflow references it, but that environment has no protection rules by default. Do not enable the PyPI publisher until the named environment is visible in repository settings with required reviewers and the intended stable-tag restriction. See [GitHub's environment management behavior](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).

### PyPI name and pending publisher

Review `pintos-utils` against [PyPI's project-name guidance](https://docs.pypi.org/project-management/choosing-a-name/) before configuring it. A `404` from the project JSON endpoint does **not** prove that the name is available. A pending publisher does not reserve a project name; another party may register it before the first authorized upload. PyPI's first-use project creation and publisher authentication are authoritative. If PyPI rejects project creation or publisher authentication, stop before upload and ask the project owner to review the name and publisher settings. Do not rename the distribution automatically.

For a package that does not yet exist on PyPI, configure the pending Trusted Publisher values below and let PyPI attempt project creation only during the first explicitly authorized publication. After PyPI creates the project, confirm that the same publisher is listed as the project's normal Trusted Publisher. Do not treat pending configuration as a reservation or proof of ownership.

### Trusted Publisher fields

Configure the publisher for the project `pintos-utils` with these exact claims:

| PyPI field | Value |
| --- | --- |
| Owner | `PINTOS-LTDA` |
| Repository | `python-utils` |
| Workflow filename | `release.yml` |
| Environment | `pypi` |

The effective PyPI publisher record must match the isolated `publish` job in `.github/workflows/release.yml`. Confirm that no additional publisher is configured. Only that job may have `id-token: write`, and no workflow may contain a static PyPI token.

## Workflow and Tag Rules

- Create a GitHub Release only for a reviewed stable tag in the exact form `vMAJOR.MINOR.PATCH`; its version must equal `[project].version` after removing `v`.
- The release workflow accepts a published, non-prerelease GitHub Release. Branch and pull request validation must not request OIDC or invoke the publisher.
- Protect creation and update of `v*` tags with a repository ruleset for authorized maintainers. The supplied maintainer identity is `ivaneyvieira`.
- Pin every third-party action to a reviewed full commit SHA. Keep a version comment beside each pin and review pins when changing an action.
- The first real PyPI upload requires an explicit release instruction and maintainer approval of the protected environment deployment.

Configure the repository in this order: review the PyPI name guidance; create and verify the protected `pypi` environment and stable-tag restrictions; add the `v*` tag ruleset; then configure PyPI's pending publisher with the exact fields above. This prevents a release from targeting a newly auto-created but unprotected environment.

## Local Checks Before a Release

Run the offline validation from the repository root:

```bash
uv sync --locked --group dev
uv run pytest --cov=pintos_utils --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy src scripts/release_preflight.py
uv run pytest tests/unit/test_release_preflight.py
uv build --no-sources
```

Inspect the wheel and sdist. Both must report package `pintos-utils`, the same version, Python `>=3.11`, the `gmail` and `mysql` extras with their declared dependencies, the source URL, MIT license metadata, and the `LICENSE` file. Confirm there is exactly one expected wheel and one sdist. Do not treat a successful local build as authorization to publish.

## Publisher Approval and Rejection Check

Before any production release, compare the actual PyPI Trusted Publisher settings with the `publish` job's OIDC claims: owner `PINTOS-LTDA`, repository `python-utils`, workflow `release.yml`, and environment `pypi`. Inspect the CI, quality, and release workflows to verify the OIDC permission boundary and absence of static credentials. Any mismatch or additional publisher blocks release readiness.

For a no-upload check, reject a controlled deployment at the protected `pypi` environment and confirm that PyPI received no distribution files. Record the date, workflow run, reviewer outcome, and no-upload observation in the release review record. Do not use an alternate project or distribution as an identity probe.

For an authorized release, the designated reviewer inspects the GitHub Release tag, successful preflight and quality jobs, and the two uploaded workflow artifacts before approving the `pypi` environment. Reject or cancel if any check is missing or unexpected. Rejection must prevent the publisher job from starting; confirm no files were uploaded before considering another attempt. Approval permits the isolated job to publish the already-built files; after completion, verify each file and its provenance as described below.

## Reviewed Action Pins

All third-party actions used by the release and quality workflows must use immutable full commit SHAs. These are the pins currently in the repository; review the upstream release and security notes when changing one.

| Action | Full commit SHA | Reviewed release |
| --- | --- | --- |
| `actions/checkout` | `3d3c42e5aac5ba805825da76410c181273ba90b1` | [v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1) |
| `actions/setup-python` | `5fda3b95a4ea91299a34e894583c3862153e4b97` | [v7.0.0](https://github.com/actions/setup-python/releases/tag/v7.0.0) |
| `astral-sh/setup-uv` | `1c37ad07a6a961277cf70c0d37d6f313000f5884` | [v10.3.0](https://github.com/astral-sh/setup-uv/releases/tag/v10.3.0) |
| `actions/upload-artifact` | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` | [v7.0.2](https://github.com/actions/upload-artifact/releases/tag/v7.0.2) |
| `actions/download-artifact` | `9000827ccba6bdab643e8b6fd33ac0654aef8333` | [v8.0.2](https://github.com/actions/download-artifact/releases/tag/v8.0.2) |
| `pypa/gh-action-pypi-publish` | `7245906fb61fa33a13554f9d5fb856fe61758086` | [v1.14.3](https://github.com/pypa/gh-action-pypi-publish/releases/tag/v1.14.3) |

## Failure Recovery

- **Tag/version mismatch, existing version, inconclusive version check, quality failure, or build failure**: stop before publication, fix the source of failure, then create a new reviewed release tag.
- **Rejected environment deployment**: no publisher job should run; confirm that no files were uploaded. A later attempt requires a fresh maintainer decision.
- **PyPI project creation or publisher authentication rejection**: stop before upload, confirm the PyPI name and exact publisher claims with the project owner, and do not switch to a static token or alternate name.
- **Upload or provenance failure**: inspect PyPI's release files and provenance for each file before any retry. PyPI can accept one distribution before a later upload fails, and published files cannot be replaced in place. Never retry an ambiguous upload blindly.
- **Missing or mismatched provenance**: do not record the release as complete. Compare each file's digest and attestation with the intended repository, tagged revision, workflow, and environment, then resolve the discrepancy before another release attempt.

## First Authorized Release Follow-up

After an explicitly authorized production upload, verify the PyPI project metadata, install the base package and Gmail extra in clean environments, and check the attestation for the wheel and sdist independently. Record evidence and any blockers in `specs/002-pypi-trusted-publishing/quickstart.md`. Do not mark these checks complete before a successful authorized release.

## References

- [PyPI Trusted Publisher setup](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
- [Create a project with a pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
- [PyPI project-name guidance](https://docs.pypi.org/project-management/choosing-a-name/)
- [GitHub deployment environments and required reviewers](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
- [PyPA publishing action](https://github.com/marketplace/actions/pypi-publish)
