"""Optional dependency and package metadata acceptance tests."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path


def test_polars_is_an_optional_extra_and_not_a_base_dependency() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())["project"]

    assert "polars" not in " ".join(project["dependencies"]).lower()
    assert project["optional-dependencies"]["polars"] == ["polars>=1.0,<3"]
    assert "--extra polars" in Path(".github/workflows/_quality.yml").read_text()


def test_base_and_existing_imports_work_when_polars_cannot_be_imported() -> None:
    script = r"""
import builtins
import importlib
original_import = builtins.__import__
def without_polars(name, *args, **kwargs):
    if name == "polars" or name.startswith("polars."):
        raise ModuleNotFoundError("blocked optional polars dependency")
    return original_import(name, *args, **kwargs)
builtins.__import__ = without_polars
original_import_module = importlib.import_module
def without_polars_module(name, package=None):
    if name == "polars" or name.startswith("polars."):
        raise ModuleNotFoundError("blocked optional polars dependency")
    return original_import_module(name, package)
importlib.import_module = without_polars_module

from pintos_utils.database import (
    DataFrameDatabaseError,
    DataFrameImportResult,
    ImportMode,
    SqlScriptExecutor,
    SqlScriptResult,
    query_dataframe,
)
from pintos_utils.email import EmailAddress, EmailMessage, EmailSender

assert ImportMode.APPEND.value == "APPEND"
assert DataFrameImportResult(0, 0).rows_processed == 0
assert SqlScriptResult().rows == []
assert SqlScriptExecutor is not None
assert EmailAddress is not None and EmailMessage is not None and EmailSender is not None
try:
    query_dataframe(object(), "SELECT 1")
except DataFrameDatabaseError as error:
    assert "pintos-utils[mysql,polars]" in str(error)
else:
    raise AssertionError("missing Polars should produce an actionable library error")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_public_dataframe_models_and_error_are_importable_without_polars() -> None:
    script = r"""
import builtins
import importlib
original_import = builtins.__import__
def without_polars(name, *args, **kwargs):
    if name == "polars" or name.startswith("polars."):
        raise ModuleNotFoundError("blocked optional polars dependency")
    return original_import(name, *args, **kwargs)
builtins.__import__ = without_polars
original_import_module = importlib.import_module
def without_polars_module(name, package=None):
    if name == "polars" or name.startswith("polars."):
        raise ModuleNotFoundError("blocked optional polars dependency")
    return original_import_module(name, package)
importlib.import_module = without_polars_module
from pintos_utils.database import (
    DataFrameDatabaseError,
    DataFrameImportResult,
    ImportMode,
)
assert DataFrameDatabaseError("missing", operation="query").operation == "query"
assert DataFrameImportResult(2, 1).rows_processed == 2
assert ImportMode.UPSERT.value == "UPSERT"
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_dataframe_operation_names_missing_mysql_extra() -> None:
    script = r"""
import builtins
import importlib
original_import = builtins.__import__
def without_mysql(name, *args, **kwargs):
    if name == "mysql" or name.startswith("mysql."):
        raise ModuleNotFoundError("blocked optional mysql dependency")
    return original_import(name, *args, **kwargs)
builtins.__import__ = without_mysql
original_import_module = importlib.import_module
def without_mysql_module(name, package=None):
    if name == "mysql" or name.startswith("mysql."):
        raise ModuleNotFoundError("blocked optional mysql dependency")
    return original_import_module(name, package)
importlib.import_module = without_mysql_module
from pintos_utils.database import DataFrameDatabaseError, query_dataframe
try:
    query_dataframe(object(), "SELECT 1")
except DataFrameDatabaseError as error:
    assert "pintos-utils[mysql,polars]" in str(error)
else:
    raise AssertionError("missing MySQL extra should produce an actionable error")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
