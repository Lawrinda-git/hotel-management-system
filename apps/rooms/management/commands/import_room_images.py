from django.core.management.base import BaseCommand
from django.conf import settings
from apps.rooms.models import Room, RoomImage
import os, re


class Command(BaseCommand):
    help = 'Import images from frontend/static/frontend/rooms/ as RoomImage records. Filenames should include room id like photo_<roomid>_...'

    def handle(self, *args, **options):
        static_dir = os.path.join(settings.BASE_DIR, 'frontend', 'static', 'frontend', 'rooms')
        if not os.path.isdir(static_dir):
            self.stderr.write(f'Rooms static directory not found: {static_dir}')
            return

        files = sorted(os.listdir(static_dir))
        created = 0
        skipped = 0
        for fname in files:
            if fname.startswith('.'):
                continue
            lower = fname.lower()
            if not (lower.endswith('.jpg') or lower.endswith('.jpeg') or lower.endswith('.png') or lower.endswith('.svg')):
                continue
            m = re.match(r'photo_(\d+)_', fname)
            if not m:
                # try room_<id> pattern
                m2 = re.match(r'room_(\d+)', fname)
                if m2:
                    room_id = int(m2.group(1))
                else:
                    self.stdout.write(f'Skipping file without room id in name: {fname}')
                    skipped += 1
                    continue
            else:
                room_id = int(m.group(1))

            try:
                room = Room.objects.get(pk=room_id)
            except Room.DoesNotExist:
                self.stdout.write(f'No Room with id={room_id} for file {fname}; skipping')
                skipped += 1
                continue

            file_path = f'frontend/rooms/{fname}'
            if RoomImage.objects.filter(file_path=file_path, room=room).exists():
                self.stdout.write(f'Image already exists for room {room_id}: {fname}')
                skipped += 1
                continue

            # compute order as next available
            from django.db.models import Max
            max_order = RoomImage.objects.filter(room=room).aggregate(Max('order'))['order__max'] or 0
            order = max_order + 1

            RoomImage.objects.create(room=room, file_path=file_path, order=order)
            self.stdout.write(f'Added image for room {room_id}: {fname} (order={order})')
            created += 1

        self.stdout.write(self.style.SUCCESS(f'Done. Created: {created}, Skipped: {skipped}'))
