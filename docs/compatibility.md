# Settings and compatibility

## Django settings

The package has no custom mandatory settings. Add
`"django_native_jsonform"` to `INSTALLED_APPS` so its templates and static
assets are discoverable.

Project-specific endpoints, permissions, media handlers, or design-system
options belong to the project's custom fields/widgets. The core library does
not read consumer settings by name.

## Supported versions

The initial package metadata supports:

- Python 3.10–3.13;
- Django 4.2 and Django 5.x.

Compatibility is exercised by the repository's CI matrix before releases.

## Browser support

The progressive JavaScript uses standard DOM APIs and no framework. Modern
evergreen browsers are supported. Without JavaScript, existing scalar values
still render and submit, but adding array items and interactively switching
conditional branches requires progressive enhancement.

## Data compatibility

The package works with ordinary Python dictionaries/lists and does not replace
`models.JSONField`. Moving a model from another JSON form widget generally does
not require changing the database column. Always inspect the generated Django
migration; a widget/form-only migration should be state-only or unnecessary.

## JSON Schema compatibility

The package consumes a practical editable subset of JSON Schema plus optional
UI keys. It does not claim validation conformance to a particular JSON Schema
draft. See [Supported JSON Schema](schema-reference.md).
