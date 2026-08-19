# Architecture

The package separates schema interpretation, Django binding, and HTML
rendering.

```text
JSONSchemaFormField
        |
        v
JSONSchemaWidget ---- resolves callable schema/context
        |
        v
SchemaBinding ------- builds Node tree + flat Django Form
   |          |
   |          +------ JSONFormRegistry / field_resolver / overrides
   v
JSONFormRenderer ---- node templates + progressive JS
        |
        v
POST -> Django fields -> reconstructed JSON-compatible Python value
```

## Flat Django form, nested logical tree

`SchemaBinding` creates a `Node` tree that represents objects, arrays, unions,
array items, and scalar leaves. It also creates a flat internal `forms.Form`.
Stable encoded names connect each leaf and presence marker to its logical path.

This design allows native Django widgets and fields to work without asking
them to understand nested JSON.

## Presence markers

HTML forms cannot distinguish an absent optional key from an empty value by
the submitted scalar alone. Hidden presence fields preserve that distinction.
They also make sparse defaults and inheritance safe.

## Arrays

An array has a server-rendered prototype containing a unique index token. The
small JavaScript layer clones it and updates indices. The server enforces a
hard `max_array_items` cap before building submitted items.

## Unions

All branch shapes are server-rendered so switching is immediate. Only the
selected branch is enabled and cleaned. A discriminator is inferred from
distinct `const`/single-enum properties or read from OpenAPI metadata.

## Trust boundaries

Client-side controls improve UX only. Posted presence, counts, branches, and
values are bounded, rebuilt, coerced, and validated on the server. Schema
callables, field factories, serializers, and templates are trusted application
code, not user-provided content.
