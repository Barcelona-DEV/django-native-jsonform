# Contributing

## Principles

- Use Django fields for parsing and validation.
- Keep browser behavior progressive and server-authoritative.
- Keep application models and endpoints out of the core package.
- Add extensibility through context, registries, resolvers, serializers, and
  templates.
- Preserve sparse and unknown JSON unless an API explicitly says otherwise.
- Treat import order and shared mutable registries carefully.

## Setup

```bash
git clone git@github.com:Barcelona-DEV/django-native-jsonform.git
cd django-native-jsonform
uv sync --all-extras
```

## Quality commands

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run coverage run -m pytest
uv run coverage report
uv build
uv run mkdocs build --strict
```

## Adding a schema keyword or format

1. Decide whether it is portable schema behavior or presentation metadata.
2. Prefer an extension registry when the behavior is domain-specific.
3. Put schema-tree behavior in `SchemaBinding`, field construction in the
   registry, and HTML only in the renderer/templates.
4. Cover unbound rendering, valid binding, invalid binding, initial values,
   sparse values, and nested array/union placement.
5. Document the keyword and compatibility implications.

## Pull requests

Keep changes focused. Update `CHANGELOG.md` under `Unreleased` for user-visible
changes. Public APIs require type hints and documentation. A release is cut
from a reviewed commit on `main` through a GitHub Release.
