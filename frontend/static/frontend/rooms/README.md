Room images directory

- Purpose: store room photos shown during booking and hotel pages.
- Recommended naming: `room_<room_id>_<index>.jpg` (e.g. `room_42_1.jpg`).
- Sizes: provide 1200x800 or 1024x768 JPG/PNG for best results; create 400x300 thumbnails if needed.
- How to use: reference images in templates with `{% static 'frontend/rooms/room_<id>_1.jpg' %}` or via model field storing the filename.
- Add real images by dropping files into this folder and collecting staticfiles (`python manage.py collectstatic`) if in production.
