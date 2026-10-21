"""Fail-closed checks for a tagged PyPI release."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

_STABLE_TAG = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_PYPI_VERSION_URL = "https://pypi.org/pypi/{name}/{version}/json"
_REQUEST_TIMEOUT_SECONDS = 10


class ReleasePreflightError(Exception):
    """Base exception for release preflight failures."""


class ReleaseValidationError(ReleasePreflightError):
    """The tag or project metadata is invalid for the release workflow."""


class ReleaseVersionError(ReleasePreflightError):
    """The release tag does not match the project or the version exists."""


class ReleaseRegistryError(ReleasePreflightError):
    """PyPI could not conclusively answer whether this version exists."""


def _read_project(project_file: Path) -> tuple[str, str]:
    try:
        document = tomllib.loads(project_file.read_text(encoding="utf-8"))
        project = document["project"]
        name = project["name"]
        version = project["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as error:
        raise ReleaseValidationError(
            f"Unable to read static project name/version from {project_file}."
        ) from error

    if not isinstance(name, str) or not name.strip():
        raise ReleaseValidationError("[project].name must be a non-empty string.")
    if not isinstance(version, str) or not version.strip():
        raise ReleaseValidationError("[project].version must be a static string.")
    return name, version


def _version_from_tag(tag: str) -> str:
    match = _STABLE_TAG.fullmatch(tag)
    if match is None:
        raise ReleaseValidationError(
            "Release tag must use stable vMAJOR.MINOR.PATCH format "
            "without leading zeroes."
        )
    return tag[1:]


def _version_is_published(name: str, version: str) -> bool:
    endpoint = _PYPI_VERSION_URL.format(name=name, version=version)
    try:
        with urlopen(endpoint, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
            if response.status == 200:
                return True
            raise ReleaseRegistryError(
                "PyPI version lookup returned inconclusive HTTP status "
                f"{response.status}."
            )
    except HTTPError as error:
        if error.code == 404:
            return False
        raise ReleaseRegistryError(
            f"PyPI version lookup returned inconclusive HTTP status {error.code}."
        ) from error
    except (URLError, TimeoutError, OSError, ValueError) as error:
        raise ReleaseRegistryError(
            "Unable to determine whether the PyPI version exists."
        ) from error


def run_release_preflight(tag: str, project_file: Path = Path("pyproject.toml")) -> str:
    """Validate the stable tag and fail if PyPI already contains that version."""
    tag_version = _version_from_tag(tag)
    project_name, project_version = _read_project(project_file)
    if tag_version != project_version:
        raise ReleaseVersionError(
            f"Release tag version {tag_version} does not match project version "
            f"{project_version}."
        )

    if _version_is_published(project_name, tag_version):
        raise ReleaseVersionError(
            f"PyPI already contains {project_name}=={tag_version}; "
            "published versions are immutable."
        )
    return tag_version


def main(argv: Sequence[str] | None = None) -> int:
    """Run the release preflight command-line interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="stable release tag, for example v1.2.3")
    parser.add_argument(
        "--project-file",
        type=Path,
        default=Path("pyproject.toml"),
        help="project metadata file (default: pyproject.toml)",
    )
    args = parser.parse_args(argv)

    try:
        version = run_release_preflight(args.tag, args.project_file)
    except ReleasePreflightError as error:
        print(f"Release preflight failed: {error}", file=sys.stderr)
        return 1

    print(f"Release preflight passed for {args.tag} ({version}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
