from django.core.management.base import BaseCommand
from django.contrib.sessions.models import Session
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Nettoyer les sessions expirées'
    
    def handle(self, *args, **options):
        # Supprimer les sessions de plus de 2 semaines
        two_weeks_ago = timezone.now() - timedelta(weeks=2)
        expired_sessions = Session.objects.filter(expire_date__lt=two_weeks_ago)
        
        count = expired_sessions.count()
        expired_sessions.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'{count} sessions expirées nettoyées')
        )