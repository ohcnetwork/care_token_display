from importlib import import_module

from django.apps import AppConfig
from django.conf import settings
from django.urls import include, path
from django.utils.translation import gettext_lazy as _

PLUGIN_NAME = "token_display"


class TokenDisplayConfig(AppConfig):
    name = PLUGIN_NAME
    verbose_name = _("Token Display")

    def ready(self):
        import token_display.signals  # noqa F401

        # include non-API routes (SSR Pages)
        urlconf = import_module(settings.ROOT_URLCONF)
        urlconf.urlpatterns += [
            path(f"{PLUGIN_NAME}/", include(f"{PLUGIN_NAME}.pages"))
        ]
