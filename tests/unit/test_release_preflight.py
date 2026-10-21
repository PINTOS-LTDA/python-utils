from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import pytest
import release_preflight
from release_preflight import (
    ReleaseRegistryError,
    ReleaseValidationError,
    ReleaseVersionError,
    run_release_preflight,
)


class FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        return None


def write_project(
    tmp_path: Path, *, name: str = "pintos-utils", version: str = "1.2.3"
) -> Path:
    project_file = tmp_path / "pyproject.toml"
    project_file.write_text(
        f'[project]\nname = "{name}"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    return project_file


def test_matching_unpublished_version_passes_with_version_endpoint_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_file = write_project(tmp_path)
    requested_urls: list[str] = []

    def return_not_found(url: str, *, timeout: float) -> FakeResponse:
        requested_urls.append(url)
        raise HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(release_preflight, "urlopen", return_not_found)

    assert run_release_preflight("v1.2.3", project_file) == "1.2.3"
    assert requested_urls == ["https://pypi.org/pypi/pintos-utils/1.2.3/json"]


def test_existing_version_blocks_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_file = write_project(tmp_path)
    monkeypatch.setattr(
        release_preflight,
        "urlopen",
        lambda url, *, timeout: FakeResponse(status=200),
    )

    with pytest.raises(
        ReleaseVersionError, match="already contains pintos-utils==1.2.3"
    ):
        run_release_preflight("v1.2.3", project_file)


@pytest.mark.parametrize("tag", ["1.2.3", "v01.2.3", "v1.02.3", "v1.2.03", "v1.2.3rc1"])
def test_malformed_or_non_stable_tag_fails_before_registry_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tag: str
) -> None:
    project_file = write_project(tmp_path)
    monkeypatch.setattr(
        release_preflight,
        "urlopen",
        lambda *args, **kwargs: pytest.fail(
            "registry must not be queried for an invalid tag"
        ),
    )

    with pytest.raises(ReleaseValidationError, match="stable vMAJOR.MINOR.PATCH"):
        run_release_preflight(tag, project_file)


def test_tag_version_mismatch_fails_before_registry_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_file = write_project(tmp_path, version="1.2.4")
    monkeypatch.setattr(
        release_preflight,
        "urlopen",
        lambda *args, **kwargs: pytest.fail(
            "registry must not be queried after a version mismatch"
        ),
    )

    with pytest.raises(
        ReleaseVersionError, match="does not match project version 1.2.4"
    ):
        run_release_preflight("v1.2.3", project_file)


@pytest.mark.parametrize(
    "failure",
    [
        URLError("network unavailable"),
        HTTPError(
            "https://pypi.org/pypi/pintos-utils/1.2.3/json",
            503,
            "Unavailable",
            None,
            None,
        ),
    ],
)
def test_inconclusive_registry_response_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    project_file = write_project(tmp_path)

    def fail_lookup(url: str, *, timeout: float) -> None:
        raise failure

    monkeypatch.setattr(release_preflight, "urlopen", fail_lookup)

    with pytest.raises(ReleaseRegistryError, match="Unable to determine|inconclusive"):
        run_release_preflight("v1.2.3", project_file)
