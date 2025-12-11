from django.apps import AppConfig

class CoreConfig(AppConfig):  # Changer GestionExamenConfig en CoreConfig
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        # Importer les signaux
        import core.signals  # noqa