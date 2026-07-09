from django.apps import AppConfig


class FutebolConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'futebol'

    def ready(self):
        from futebol.services.gates import register_gates

        register_gates()
