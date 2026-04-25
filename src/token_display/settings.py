from typing import Any

import environ
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.signals import setting_changed
from django.dispatch import receiver
from rest_framework.settings import perform_import

from token_display.apps import PLUGIN_NAME

env = environ.Env()


class PluginSettings:  # pragma: no cover
    """
    A settings object that allows plugin settings to be accessed as
    properties. For example:

        from plugin.settings import plugin_settings
        print(plugin_settings.API_KEY)

    Any setting with string import paths will be automatically resolved
    and return the class, rather than the string literal.

    """

    def __init__(
        self,
        plugin_name: str = None,
        defaults: dict | None = None,
        import_strings: set | None = None,
        required_settings: set | None = None,
    ) -> None:
        if not plugin_name:
            raise ValueError("Plugin name must be provided")
        self.plugin_name = plugin_name
        self.defaults = defaults or {}
        self.import_strings = import_strings or set()
        self.required_settings = required_settings or set()
        self._cached_attrs = set()
        self.validate()

    def __getattr__(self, attr) -> Any:
        if attr not in self.defaults:
            raise AttributeError("Invalid setting: '%s'" % attr)

        # Try to find the setting from user settings, then from environment variables
        val = self.defaults[attr]
        try:
            val = self.user_settings[attr]
        except KeyError:
            try:
                val = env(attr, cast=type(val))
            except environ.ImproperlyConfigured:
                # Fall back to defaults
                pass

        # Coerce import strings into classes
        if attr in self.import_strings:
            val = perform_import(val, attr)

        self._cached_attrs.add(attr)
        setattr(self, attr, val)
        return val

    @property
    def user_settings(self) -> dict:
        if not hasattr(self, "_user_settings"):
            self._user_settings = getattr(settings, "PLUGIN_CONFIGS", {}).get(
                self.plugin_name, {}
            )
        return self._user_settings

    def validate(self) -> None:
        """
        This method handles the validation of the plugin settings.
        It could be overridden to provide custom validation logic.

        the base implementation checks if all the required settings are truthy.
        """
        for setting in self.required_settings:
            if not getattr(self, setting):
                raise ImproperlyConfigured(
                    f'The "{setting}" setting is required. '
                    f'Please set the "{setting}" in the environment or the {PLUGIN_NAME} plugin config.'
                )

    def reload(self) -> None:
        """
        Deletes the cached attributes so they will be recomputed next time they are accessed.
        """
        for attr in self._cached_attrs:
            delattr(self, attr)
        self._cached_attrs.clear()
        if hasattr(self, "_user_settings"):
            delattr(self, "_user_settings")


REQUIRED_SETTINGS = set()

# Default Piper voice catalog. Each entry maps a voice id to download URLs for
# its ONNX model and matching JSON config (Rhasspy/Piper Hugging Face mirror).
# Operators may override / extend this via PLUGIN_CONFIGS or env.
_PIPER_HF_BASE = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
)
_DEFAULT_VOICE_CATALOG = {
    "en_US-amy-medium": {
        "lang": "en-US",
        "onnx_url": f"{_PIPER_HF_BASE}/en/en_US/amy/medium/en_US-amy-medium.onnx",
        "config_url": f"{_PIPER_HF_BASE}/en/en_US/amy/medium/en_US-amy-medium.onnx.json",
    },
    "en_US-ryan-high": {
        "lang": "en-US",
        "onnx_url": f"{_PIPER_HF_BASE}/en/en_US/ryan/high/en_US-ryan-high.onnx",
        "config_url": f"{_PIPER_HF_BASE}/en/en_US/ryan/high/en_US-ryan-high.onnx.json",
    },
    "en_GB-alan-medium": {
        "lang": "en-GB",
        "onnx_url": f"{_PIPER_HF_BASE}/en/en_GB/alan/medium/en_GB-alan-medium.onnx",
        "config_url": f"{_PIPER_HF_BASE}/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json",
    },
    "hi_IN-pratham-medium": {
        "lang": "hi-IN",
        "onnx_url": f"{_PIPER_HF_BASE}/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx",
        "config_url": f"{_PIPER_HF_BASE}/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx.json",
    },
    "hi_IN-priyamvada-medium": {
        "lang": "hi-IN",
        "onnx_url": f"{_PIPER_HF_BASE}/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx",
        "config_url": f"{_PIPER_HF_BASE}/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx.json",
    },
    "ml_IN-arjun-medium": {
        "lang": "ml-IN",
        "onnx_url": f"{_PIPER_HF_BASE}/ml/ml_IN/arjun/medium/ml_IN-arjun-medium.onnx",
        "config_url": f"{_PIPER_HF_BASE}/ml/ml_IN/arjun/medium/ml_IN-arjun-medium.onnx.json",
    },
    "ml_IN-meera-medium": {
        "lang": "ml-IN",
        "onnx_url": f"{_PIPER_HF_BASE}/ml/ml_IN/meera/medium/ml_IN-meera-medium.onnx",
        "config_url": f"{_PIPER_HF_BASE}/ml/ml_IN/meera/medium/ml_IN-meera-medium.onnx.json",
    },
}

DEFAULTS = {
    "AUTO_REFRESH_INTERVAL": 0,
    "TTS_ENABLED": True,
    "TTS_DEFAULT_VOICE": "en_US-amy-medium",
    # Empty string means "resolve to <tempdir>/care_token_display_tts at runtime".
    "TTS_CACHE_DIR": "",
    "TTS_VOICE_CATALOG": _DEFAULT_VOICE_CATALOG,
}

plugin_settings = PluginSettings(
    PLUGIN_NAME, defaults=DEFAULTS, required_settings=REQUIRED_SETTINGS
)


@receiver(setting_changed)
def reload_plugin_settings(*args, **kwargs) -> None:
    setting = kwargs["setting"]
    if setting == "PLUGIN_CONFIGS":
        plugin_settings.reload()
