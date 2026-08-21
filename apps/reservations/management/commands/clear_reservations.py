from django.core.management.base import BaseCommand
from apps.reservations.models import Reservation


class Command(BaseCommand):
    help = "Clear reservations. Use --all to delete ALL reservations; otherwise pass --before YYYY-MM-DD to delete older ones."

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Delete all reservations')
        parser.add_argument('--before', type=str, help='Delete reservations with check_out before this date (YYYY-MM-DD)')

    def handle(self, *args, **options):
        if not options.get('all') and not options.get('before'):
            self.stdout.write(self.style.ERROR('Specify --all or --before YYYY-MM-DD'))
            return

        qs = Reservation.objects.all()
        if options.get('before'):
            from datetime import datetime
            try:
                cutoff = datetime.fromisoformat(options['before'])
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid date format for --before. Use YYYY-MM-DD'))
                return
            qs = qs.filter(check_out__lt=cutoff)

        count = qs.count()
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {count} reservations'))
