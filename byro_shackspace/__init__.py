from django.apps import AppConfig


class PluginConfig(AppConfig):
    name = 'byro_shackspace'

    class ByroPluginMeta:
        name = 'shackspace'

    def ready(self):
        from . import utils  # noqa


default_app_config = 'byro_shackspace.PluginConfig'
