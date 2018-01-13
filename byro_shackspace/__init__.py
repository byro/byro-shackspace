from django.apps import AppConfig


class ShackspacePluginConfig(AppConfig):
    name = 'byro_shackspace'

    class ShackspacePluginMeta:
        name = 'shackspace'

    def ready(self):
        print('fooooo')
        from . import utils


default_app_config = 'byro_shackspace.ShackspacePluginConfig'
