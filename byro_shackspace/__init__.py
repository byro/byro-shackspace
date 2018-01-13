from django.apps import AppConfig


class ShackspacePluginConfig(AppConfig):
    name = 'byro_shackspace'

    class ShackspacePluginMeta:
        name = 'shackspace'

    def ready(self):
        from . import utils  # noqa


default_app_config = 'byro_shackspace.ShackspacePluginConfig'
