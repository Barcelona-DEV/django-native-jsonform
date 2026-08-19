# Release and PyPI publishing

Releases are designed for GitHub Actions and PyPI Trusted Publishing, so no
long-lived PyPI API token needs to be stored in repository secrets.

## One-time PyPI setup

After the first project is created on PyPI, configure a Trusted Publisher:

- Owner: `Barcelona-DEV`
- Repository: `django-native-jsonform`
- Workflow: `release.yml`
- Environment: `pypi`

Create a protected GitHub environment named `pypi` and optionally require
reviewers.

## Release checklist

1. Update the version in `pyproject.toml`.
2. Move changelog entries from `Unreleased` into a dated version section.
3. Merge the release pull request into `main`.
4. Create a GitHub Release tagged `vX.Y.Z`.
5. The release workflow builds the sdist/wheel, checks their metadata, and
   publishes them using OIDC.
6. Confirm the package page and installation in a clean environment.

## Documentation publishing

The documentation workflow deploys this versioned `docs/` wiki to GitHub Pages
from `main`. Repository settings must use **GitHub Actions** as the Pages source.

The documentation is kept in the main repository so edits are reviewed beside
the code and remain available in source distributions.

## TestPyPI

For a release rehearsal, create a separate manual workflow or run:

```bash
uv build
uv publish --publish-url https://test.pypi.org/legacy/
```

Do not publish a production version number to TestPyPI if the same immutable
artifact/version will later be needed on PyPI; use a development suffix.
