SECRET_KEY = "django-native-jsonform-tests"
USE_TZ = True
STATIC_URL = "static/"
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django_native_jsonform",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
    }
]
