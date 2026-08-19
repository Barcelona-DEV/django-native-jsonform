# Contributing

Issues and pull requests are welcome.

## Local setup

```bash
git clone git@github.com:Barcelona-DEV/django-native-jsonform.git
cd django-native-jsonform
uv sync --all-extras
```

## Development commands

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build
uv run mkdocs serve
```

Add focused coverage for behavioral changes and update the wiki when a public
API changes. Do not couple the core registry to an application-specific model,
widget, URL, or permission system; expose those integrations as examples or
consumer-owned extensions.

See the [contributor guide](docs/contributing.md) for architecture and release
details.
