from django.apps import AppConfig


class BusinessConfig(AppConfig):
    name = 'apps.business'

    def ready(self):
        import apps.business.signals
