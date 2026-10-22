# pintos-utils

Reusable Python utilities for application projects. The package is framework
independent and keeps provider-specific integrations optional.

## Installation

Install the published base package from PyPI:

```bash
python -m pip install pintos-utils
uv add pintos-utils
```

For Gmail support and its optional Google dependencies:

```bash
python -m pip install "pintos-utils[gmail]"
uv add "pintos-utils[gmail]"
```

For MySQL SQL script execution and its optional driver/parser dependencies:

```bash
python -m pip install "pintos-utils[mysql]"
uv add "pintos-utils[mysql]"
```

Install the base package from a local checkout:

```bash
uv pip install .
```

For editable development:

```bash
uv pip install -e .
```

Install the Gmail integration and its optional dependencies when needed:

```bash
uv pip install "pintos-utils[gmail] @ git+ssh://git@<git-host>/<org>/pintos-utils.git@<tag-or-commit>"
```

The base package has no third-party runtime dependencies. Configure SSH access
using the consuming environment; do not put credentials in the Git URL.

## Email module

See [docs/email.md](docs/email.md) for the provider-neutral API, Gmail OAuth
ownership, error behavior, and installation examples.

## Database module

See [docs/database.md](docs/database.md) for MySQL script execution, named
parameter binding, transaction ownership, and supported SQL limitations.

## Development

Use Python 3.11 and uv to create the environment and install development tools:

```bash
uv sync --group dev
```

Run the tests, lint, formatting check, type check, and package build:

```bash
uv run pytest --cov=pintos_utils --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```
