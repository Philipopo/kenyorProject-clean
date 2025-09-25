# warehouse/apps.py
from django.apps import AppConfig

class WarehouseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'warehouse'

    def ready(self):
        pass  # No database queries or model imports