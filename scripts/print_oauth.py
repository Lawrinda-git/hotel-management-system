import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.conf import settings
print('GOOGLE_OAUTH_CLIENT_ID=', settings.GOOGLE_OAUTH_CLIENT_ID)
print('GOOGLE_OAUTH_CLIENT_SECRET=', '***' if settings.GOOGLE_OAUTH_CLIENT_SECRET else '')
print('GOOGLE_OAUTH_REDIRECT_URI=', settings.GOOGLE_OAUTH_REDIRECT_URI)
print('GOOGLE_OAUTH_REDIRECT_URIS=', settings.GOOGLE_OAUTH_REDIRECT_URIS)
print('BASE_URL=', settings.BASE_URL)
print('CSRF_TRUSTED_ORIGINS=', settings.CSRF_TRUSTED_ORIGINS)
