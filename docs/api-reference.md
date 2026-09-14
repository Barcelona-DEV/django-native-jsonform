# Public API

Import public classes from `django_native_jsonform`.

## Forms and fields

### `JSONSchemaFormField`

Composite Django field. Required keyword argument: `schema` (dictionary, boolean or
callable). Optional arguments:

- `registry` — `JSONFormRegistry`; defaults to a clone of
  `default_registry`;
- `overrides` — mapping of path patterns to dictionaries/callables;
- `field_resolver` — fallback leaf factory;
- `renderer` or `templates` — rendering customization;
- `default_policy` — `preserve` (default) or `materialize`;
- `preserve_unknown` — preserve undeclared object keys, default `True`;
- `max_array_items` — safety cap, default `250`;
- `max_depth`, `max_nodes` — editor budgets, defaults `32` and `5000`;
- `schema_resources` — referenced schemas keyed by URI;
- `schema_registry` — optional `referencing.Registry`;
- `validate_formats` — opt-in document format validation, default `False`;
- `format_checker` — optional `jsonschema.FormatChecker`;
- `max_errors` — maximum collected document errors, default `100`;
- `widget_attrs` — attributes for the composite root;
- normal Django `Field` keyword arguments.

### `JSONSchemaFormMixin`

Adds context and seeds initial bindings. Place it before `forms.Form` or an
existing form class.

### `JSONSchemaModelFormMixin`

Semantic ModelForm mixin alias.

### `JSONSchemaModelForm`

Convenience base combining `JSONSchemaModelFormMixin` and `forms.ModelForm`.

## Admin

### `JSONSchemaAdminMixin`

Builds a per-request contextual form. Override
`get_json_form_context(request, obj=None)` to extend context.

## Registry

### Document validation

`JSONSchemaValidator(schema, *, schema_registry=None, schema_resources=None,
validate_formats=False, format_checker=None, max_errors=100)` is callable and
raises `JSONFormValidationError`. Its `issues(value)` returns `SchemaIssue`
objects containing `path`, `schema_path`, `keyword`, `message` and `pointer`.
`normalize_schema(schema)` returns a copy with legacy UI extensions normalized.

### `JSONFormRegistry`

- `clone()` returns an independent shallow copy of registered factories.
- `register_field(json_type, factory=None, *, format=None)` supports direct and
  decorator forms.
- `register_widget(name, factory=None)` supports direct and decorator forms.
- `create_field(context)` and `create_widget(...)` are normally called by the
  binding engine.

### `FieldFactoryContext`

Immutable dataclass with `path`, `schema`, `required`, `disabled`, and
`form_context`.

### `WidgetFactoryContext`

Immutable dataclass with `path`, `schema`, and `form_context`.

### `default_registry`

Contains standard scalar field factories and the `textarea`, `hidden`, and
`color` widgets. `JSONSchemaWidget` clones it per widget instance.

## Overrides and validation

### `BuildContext`

Context passed to override callables, explicit field/widget factories, and a
`field_resolver`.

### `JSONFormValidationError`

Django `ValidationError` subclass accepting `errors={path: message_or_list}` to
attach errors to generated descendants.

## Rendering

### `JSONFormRenderer`

Template-based renderer. Pass a templates mapping to its constructor or
subclass `render()` / `render_node()`.

### `JSONSchemaWidget`

Composite widget used by `JSONSchemaFormField`. Most applications configure it
through the field rather than instantiating it directly.
