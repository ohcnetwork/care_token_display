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
        """
        Import models, signals, and other dependencies here to ensure
        Django's app registry is fully initialized before use.
        """

        from care.emr.registries.device_type.device_registry import DeviceTypeRegistry
        from token_display.device import TokenDisplayDevice

        # Register Device Type
        DeviceTypeRegistry.register("token-display", TokenDisplayDevice)

        # Include Non-API routes (SSR Pages)
        urlconf = import_module(settings.ROOT_URLCONF)
        urlconf.urlpatterns += [
            path(f"{PLUGIN_NAME}/", include(f"{PLUGIN_NAME}.pages"))
        ]
