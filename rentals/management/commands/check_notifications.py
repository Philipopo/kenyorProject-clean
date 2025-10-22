# rentals/management/commands/check_notifications.py

from django.core.management.base import BaseCommand
from rentals.models import Rental

class Command(BaseCommand):
    help = 'Check and generate rental notifications'

    def handle(self, *args, **options):
        rentals = Rental.objects.filter(returned=False)
        for rental in rentals:
            rental.check_notifications()
        self.stdout.write(self.style.SUCCESS('Notifications checked successfully.'))