from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from quiz_app.models import Room


class Command(BaseCommand):
    help = 'Cleanup stale quiz rooms and participants.'

    def handle(self, *args, **options):
        now = timezone.now()
        ended_threshold = now - timedelta(hours=4)
        stale_threshold = now - timedelta(days=1)

        ended_rooms = Room.objects.filter(is_ended=True, ended_at__lt=ended_threshold)
        stale_rooms = Room.objects.filter(is_started=False, created_at__lt=stale_threshold)

        ended_count = ended_rooms.count()
        stale_count = stale_rooms.count()

        if ended_count:
            ended_rooms.delete()

        if stale_count:
            stale_rooms.delete()

        self.stdout.write(self.style.SUCCESS(
            f'Cleanup complete: {ended_count} ended rooms removed, {stale_count} stale rooms removed.'
        ))
