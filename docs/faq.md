# Frequently asked questions

## Does this replace `models.JSONField`?

No. Keep using Django's native model field. This package supplies a form field
and widget for editing its value.

## Is it a complete JSON Schema validator?

No. It implements an editable subset and delegates validation to Django
fields. Add whole-value validators for domain rules or unsupported keywords.

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
