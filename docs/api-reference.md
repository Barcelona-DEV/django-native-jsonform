# Public API

Import public classes from `django_native_jsonform`.

## Forms and fields

### `JSONSchemaFormField`

Composite Django field. Required keyword argument: `schema` (dictionary or
callable). Optional arguments:

- `registry` — `JSONFormRegistry`; defaults to a clone of
  `default_registry`;
- `overrides` — mapping of path patterns to dictionaries/callables;
- `field_resolver` — fallback leaf factory;
- `renderer` or `templates` — rendering customization;
- `default_policy` — `preserve` (default) or `materialize`;
- `preserve_unknown` — preserve undeclared object keys, default `True`;
- `max_array_items` — safety cap, default `250`;
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
