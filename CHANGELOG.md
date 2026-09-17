# Changelog

All notable changes are documented here. The project follows
[Semantic Versioning](https://semver.org/) and the structure from
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- Optional DRF schema-backed object serializer factory and JSON attribute field.
- Opt-in recursive JSON:API input/output key formatting with collision detection.
- Shared JSON Schema validation, context-selected schemas, explicit references,
  complete-document PATCH semantics, and JSON Pointer validation errors.
- Integration documentation and CI coverage for optional REST dependencies.

## [0.3.1] - 2026-09-17

### Fixed

- Recurse into `oneOf` branches even when their parent declares `type: object`
  or an object default, including inside arrays and local references.
- Render nullable numbers and integers as native numeric controls rather than
  a type selector and a JSON textarea. Document constraints remain enforced.
- Cover nested rendering and lossless submission at multiple depths.

## [0.3.0] - 2026-09-14

### Changed

- Optional fields and sections are editable without Use/remove buttons by default.
- Automatic presence omits cleared optional values and empty sections while
  preserving existing empty values, numeric zero, false and read-only values.
- `presence_mode="explicit"` restores presence controls globally or by path.
- Required values and the completed document remain subject to schema validation.
- Regression coverage added; tests intentionally not executed.

## [0.2.0] - 2026-09-14

### Added

- Draft 2020-12 document validation independent of Django widgets, using
  `jsonschema` and explicit `referencing` resources with no automatic network I/O.
- Composition, conditionals, property and tuple constraints, boolean/nullable
  schemas, contains/unevaluated rules, exclusive bounds, anchors and dynamic refs.
- Opt-in document format checking, structured JSON Pointer errors and error limits.
- Native JSON fallback for complex schemas, replaceable through path overrides.
- Configurable depth/node budgets and lossless handling of large initial arrays.

### Fixed

- Browser add/remove limits, including zero maximum; removed slots are reusable.
- Nested branch/presence changes no longer re-enable deleted or inactive controls.
- Optional absent values are not validated as if present; strings preserve spaces.
- JSON numeric/boolean uniqueness and decimal `multipleOf` document validation.

### Migration notes for 0.2.0

- Previously ignored schema constraints now reject invalid documents, including
  values produced by custom serializers. Review saved configurations first.
- `required` enforces presence; use `minLength` for non-empty strings.
- Some previously unsupported schemas now render a JSON textarea for the subtree.
- Content keywords remain annotations and document format checks default to off.
- Regression tests added; not executed during this implementation by request.

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

[Unreleased]: https://github.com/Barcelona-DEV/django-native-jsonform/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Barcelona-DEV/django-native-jsonform/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Barcelona-DEV/django-native-jsonform/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/Barcelona-DEV/django-native-jsonform/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Barcelona-DEV/django-native-jsonform/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Barcelona-DEV/django-native-jsonform/releases/tag/v0.1.0
