# Changelog

All notable changes are documented here. The project follows
[Semantic Versioning](https://semver.org/) and the structure from
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [0.1.2] - 2026-08-20

### Fixed

- Infer scalar and array `oneOf` branches from persisted JSON values and
  hydrate the selected native Django widget with the existing value.

## [0.1.1] - 2026-08-20

### Changed

- Added package metadata and CI coverage for Django 6.0 on Python 3.12+.

## [0.1.0] - 2026-08-19

### Added

- Native Django form generation for JSON Schema objects, arrays, scalar
  values, choices, local references, and discriminated `oneOf` branches.
- Dynamic schemas and request-aware Django admin integration.
- Per-path field, widget, serializer, permission, default, and template
  overrides.
- Extensible field/widget registry.
- Sparse and unknown JSON preservation.
- Path-aware validation errors.
- Versioned documentation wiki and GitHub publishing workflows.

[Unreleased]: https://github.com/Barcelona-DEV/django-native-jsonform/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/Barcelona-DEV/django-native-jsonform/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Barcelona-DEV/django-native-jsonform/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Barcelona-DEV/django-native-jsonform/releases/tag/v0.1.0
