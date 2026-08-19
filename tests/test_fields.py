from django import forms
from django.test import SimpleTestCase

from django_native_jsonform import (
    FieldFactoryContext,
    JSONFormValidationError,
    JSONSchemaFormField,
    JSONSchemaFormMixin,
    default_registry,
)

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "title": "Title", "required": True},
        "description": {
            "type": "string",
            "title": "Description",
            "widget": "textarea",
        },
        "color": {
            "type": "string",
            "format": "color",
            "default": "#123456",
        },
    },
}


class ExampleForm(JSONSchemaFormMixin, forms.Form):
    settings = JSONSchemaFormField(schema=SCHEMA)


class JSONSchemaFormFieldTests(SimpleTestCase):
    def test_renders_native_django_widgets_from_schema(self):
        form = ExampleForm(initial={"settings": {"title": "Example"}})

        html = str(form["settings"])

        self.assertIn('name="settings-title"', html)
        self.assertIn('name="settings-description"', html)
        self.assertIn("<textarea", html)
        self.assertIn('type="color"', html)

    def test_reconstructs_json_and_preserves_unknown_keys(self):
        form = ExampleForm(
            data={
                "settings-title": "Changed",
                "settings-__jsonform_present__title": "True",
                "settings-description": "Long description",
                "settings-__jsonform_present__description": "True",
                # A displayed schema default is deliberately not materialized.
                "settings-color": "#123456",
                "settings-__jsonform_present__color": "False",
            },
            initial={
                "settings": {
                    "title": "Before",
                    "unknown": {"kept": True},
                }
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["settings"],
            {
                "title": "Changed",
                "description": "Long description",
                "unknown": {"kept": True},
            },
        )

    def test_unchanged_sparse_json_is_not_reported_as_changed(self):
        form = ExampleForm(
            data={
                "settings-__jsonform_present____root_value__": "True",
                "settings-title": "Before",
                "settings-__jsonform_present__title": "True",
                "settings-description": "",
                "settings-__jsonform_present__description": "False",
                "settings-color": "#123456",
                "settings-__jsonform_present__color": "False",
            },
            initial={
                "settings": {
                    "title": "Before",
                    "unknown": {"kept": True},
                }
            },
        )

        self.assertFalse(form.has_changed())

    def test_can_materialize_defaults_globally_or_per_path(self):
        class MaterializedForm(JSONSchemaFormMixin, forms.Form):
            settings = JSONSchemaFormField(
                schema=SCHEMA,
                default_policy="materialize",
                overrides={"description": {"default_policy": "preserve"}},
            )

        form = MaterializedForm(
            data={
                "settings-title": "New",
                "settings-__jsonform_present__title": "True",
                "settings-color": "#123456",
                "settings-__jsonform_present__color": "True",
            },
            initial={"settings": {}},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["settings"]["color"], "#123456")
        self.assertNotIn("description", form.cleaned_data["settings"])

    def test_nested_object_defaults_do_not_become_declared_values(self):
        schema = {
            "type": "object",
            "properties": {
                "colors": {
                    "type": "object",
                    "default": {"primary": "#112233", "secondary": "#ffffff"},
                    "properties": {
                        "primary": {"type": "string", "format": "color"},
                        "secondary": {"type": "string", "format": "color"},
                    },
                }
            },
        }

        class ColorsForm(JSONSchemaFormMixin, forms.Form):
            settings = JSONSchemaFormField(schema=schema)

        form = ColorsForm(
            data={
                "settings-colors__primary": "#112233",
                "settings-colors__secondary": "#ffffff",
                "settings-__jsonform_present__colors": "False",
                "settings-__jsonform_present__colors__primary": "False",
                "settings-__jsonform_present__colors__secondary": "False",
            },
            initial={"settings": {"title": "Keep me"}},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["settings"], {"title": "Keep me"})

    def test_supports_nested_arrays_of_objects(self):
        schema = {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "points": {"type": "integer", "minimum": 0},
                        },
                        "required": ["name", "points"],
                    },
                }
            },
            "required": ["rows"],
        }

        class RowsForm(JSONSchemaFormMixin, forms.Form):
            settings = JSONSchemaFormField(schema=schema)

        form = RowsForm(
            data={
                "settings-__jsonform_present__rows": "True",
                "settings-__jsonform_count__rows": "2",
                "settings-rows__0__name": "First",
                "settings-rows__0__points": "10",
                "settings-rows__1__name": "Second",
                "settings-rows__1__points": "20",
            },
            initial={"settings": {"rows": []}},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["settings"]["rows"],
            [
                {"name": "First", "points": 10},
                {"name": "Second", "points": 20},
            ],
        )

    def test_supports_one_of_and_drops_fields_from_previous_branch(self):
        schema = {
            "type": "object",
            "properties": {
                "source": {
                    "oneOf": [
                        {
                            "title": "Feed",
                            "properties": {
                                "type": {"const": "feed"},
                                "url": {"type": "string"},
                            },
                            "required": ["type", "url"],
                        },
                        {
                            "title": "Manual",
                            "properties": {
                                "type": {"const": "manual"},
                                "notes": {"type": "string"},
                            },
                            "required": ["type"],
                        },
                    ]
                }
            },
            "required": ["source"],
        }

        class UnionForm(JSONSchemaFormMixin, forms.Form):
            settings = JSONSchemaFormField(schema=schema)

        form = UnionForm(
            data={
                "settings-__jsonform_variant__source": "manual",
                "settings-source____branch_1____notes": "Entered manually",
                "settings-__jsonform_present__source____branch_1____notes": "True",
            },
            initial={
                "settings": {"source": {"type": "feed", "url": "https://example.test"}}
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["settings"]["source"],
            {"type": "manual", "notes": "Entered manually"},
        )

        html = str(
            UnionForm(initial={"settings": {"source": {"type": "feed", "url": ""}}})[
                "settings"
            ]
        )
        self.assertIn('data-jsonform-discriminator="type"', html)
        self.assertIn('value="manual"', html)
        self.assertIn('data-jsonform-branch-value="manual"', html)

    def test_field_widget_serializer_and_path_errors_are_customizable(self):
        def validate(settings):
            if settings.get("profile", {}).get("bio") == "NOPE":
                raise JSONFormValidationError(
                    "Invalid profile",
                    errors={"profile.bio": "This biography is rejected."},
                )

        schema = {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "object",
                    "properties": {"bio": {"type": "string"}},
                    "required": ["bio"],
                }
            },
            "required": ["profile"],
        }

        class CustomForm(JSONSchemaFormMixin, forms.Form):
            settings = JSONSchemaFormField(
                schema=schema,
                overrides={
                    "profile.bio": {
                        "field": forms.CharField(max_length=8),
                        "widget": forms.Textarea(attrs={"class": "custom-bio"}),
                        "serialize": str.upper,
                    }
                },
                validators=[validate],
            )

        unbound = CustomForm(initial={"settings": {"profile": {"bio": "hello"}}})
        self.assertIn("custom-bio", str(unbound["settings"]))

        form = CustomForm(
            data={
                "settings-profile__bio": "nope",
                "settings-__jsonform_present__profile__bio": "True",
            },
            initial={"settings": {"profile": {"bio": "before"}}},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("This biography is rejected.", str(form["settings"]))

    def test_callable_schema_receives_form_context(self):
        def schema(context):
            return {
                "type": "object",
                "properties": {
                    "tenant": {
                        "type": "string",
                        "default": context.tenant,
                    }
                },
            }

        class ContextForm(JSONSchemaFormMixin, forms.Form):
            settings = JSONSchemaFormField(schema=schema)

        form = ContextForm(
            initial={"settings": {}},
            json_form_context={"tenant": "acme"},
        )

        self.assertIn('value="acme"', str(form["settings"]))

    def test_custom_format_can_use_a_project_specific_field(self):
        registry = default_registry.clone()

        @registry.register_field("string", format="asset")
        def asset_field(context: FieldFactoryContext):
            return forms.CharField(
                label=context.schema["title"],
                widget=forms.TextInput(attrs={"data-asset-picker": ""}),
            )

        schema = {
            "type": "object",
            "properties": {
                "image": {
                    "type": "string",
                    "format": "asset",
                    "title": "Image",
                }
            },
        }

        class AssetForm(JSONSchemaFormMixin, forms.Form):
            settings = JSONSchemaFormField(schema=schema, registry=registry)

        html = str(AssetForm(initial={"settings": {}})["settings"])

        self.assertIn("data-asset-picker", html)
