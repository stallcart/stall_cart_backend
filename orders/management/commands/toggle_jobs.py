# orders/management/commands/toggle_jobs.py
from django.core.management.base import BaseCommand
from common.models import SiteSettings

class Command(BaseCommand):
    help = "Enable or disable background sync and email jobs globally in Site Settings."

    def add_arguments(self, parser):
        parser.add_argument('action', choices=['start', 'stop', 'status'], help="Action to perform: start, stop, or status")

    def handle(self, *args, **options):
        action = options['action']
        settings = SiteSettings.get_singleton()
        
        if action == 'start':
            settings.enable_background_jobs = True
            settings.save(update_fields=['enable_background_jobs'])
            self.stdout.write(self.style.SUCCESS("Background jobs have been ENABLED successfully."))
        elif action == 'stop':
            settings.enable_background_jobs = False
            settings.save(update_fields=['enable_background_jobs'])
            self.stdout.write(self.style.WARNING("Background jobs have been DISABLED successfully."))
        elif action == 'status':
            status = "ENABLED (Running)" if settings.enable_background_jobs else "DISABLED (Stopped)"
            self.stdout.write(f"Background jobs global status: {status}")
