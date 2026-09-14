# Frequently asked questions

## Does this replace `models.JSONField`?

No. Keep using Django's native model field. This package supplies a form field
and widget for editing its value.

## Is it a complete JSON Schema validator?

Document validation delegates to `jsonschema` Draft 2020-12 after Django fields
are cleaned. Not every keyword has a generated visual editor: complex subtrees
use a replaceable native JSON textarea. Formats are opt-in at the document
layer and content keywords are annotations. See the [schema reference](schema-reference.md).

## Can it use my existing Django widget?

Yes. Supply it in a path override, register it by name, or return a custom
Django field that already owns the widget.

## Can schemas depend on the current user?

Yes. Use a callable schema and pass `json_form_context`, or add
`JSONSchemaAdminMixin` in admin.

## Will unknown JSON keys be deleted?

Not by default. `preserve_unknown=True` keeps them. Set it to `False` only for
forms that own the entire JSON object.

## Why did a displayed default not get saved?

The default policy is intentionally `preserve`: a missing key stays missing
until it becomes present. Choose `default_policy="materialize"` when displayed
defaults must be written.

## Does it require JavaScript?

Server validation does not. Interactive array creation and union switching do.
