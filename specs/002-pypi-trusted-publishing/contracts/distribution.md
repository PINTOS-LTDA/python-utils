# PyPI Distribution Contract

## Package Identity

- PyPI distribution name: `pintos-utils`.
- Python import package: `pintos_utils`.
- Source repository: `https://github.com/PINTOS-LTDA/python-utils`.
- Version authority: static `[project].version` in `pyproject.toml`.
- Supported Python: `>=3.11`.
- Release versions: stable Semantic Versioning `MAJOR.MINOR.PATCH`, represented by the Git tag `vMAJOR.MINOR.PATCH`.

## Release Files

Every release contains:

1. A universal Python wheel, expected to be tagged as `py3-none-any` for this pure-Python package.
2. A source distribution archive (`.tar.gz`).

Both files must have the normalized project name and identical version. They are built from the same source revision, retain the selected project metadata, and include the MIT license file and license metadata. The exact copyright holder name and year must be supplied by the authorized rights holder before the initial upload.

## Runtime Dependencies

- Base install has no third-party runtime dependencies.
- Optional extra `gmail` provides Gmail integration dependencies.
- No web framework or build/CI tool is installed as a runtime dependency.

## Required Package Metadata

The built metadata must accurately expose the project name, version, README description, Python minimum, optional `gmail` extra and its dependencies, source repository URL, and the approved MIT license. Use PEP 639 `license = "MIT"` and `license-files = ["LICENSE"]`. Do not add author/maintainer identity that the project has not supplied.

## Consumer Installation Examples

After publication, base installation is:

```bash
python -m pip install pintos-utils
```

For the Gmail provider and its optional dependencies:

```bash
python -m pip install "pintos-utils[gmail]"
```

With uv:

```bash
uv add pintos-utils
uv add "pintos-utils[gmail]"
```

Existing local, editable, and private Git installation methods remain documented for project contributors and applications with repository access.
