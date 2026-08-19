# Installation

## From PyPI

```bash
python -m pip install django-native-jsonform
```

With Poetry or uv:

```bash
poetry add django-native-jsonform
uv add django-native-jsonform
```

Add the application so Django discovers its templates and static assets:

```python
INSTALLED_APPS = [
    # Django and project applications...
    "django_native_jsonform",
]
```

No URL configuration, model migration, or database table is required.

## Requirements

- Python 3.10 or newer.
- Django 4.2 through 5.x.
- A normal Django template backend with `APP_DIRS=True`, or equivalent template
  loaders.
- Django staticfiles configured in environments where the widget is rendered.

## Development installation

```bash
git clone git@github.com:Barcelona-DEV/django-native-jsonform.git
cd django-native-jsonform
uv sync --all-extras
```

Use an editable checkout from another project with:

```bash
python -m pip install -e ../django-native-jsonform
```

## Confirm the installation

```bash
python manage.py check
```

The package has no models, so `makemigrations` should not create a migration
for it.
