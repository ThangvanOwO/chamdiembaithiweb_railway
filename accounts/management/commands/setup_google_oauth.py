"""
Auto-provision Google OAuth SocialApp + SocialToken from environment variables.
Run on every deploy so the DB SocialApp stays in sync with env vars.
Env vars: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'Tạo / cập nhật Google SocialApp từ biến môi trường'

    def handle(self, *args, **options):
        client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')

        if not client_id or not client_secret:
            self.stdout.write(self.style.WARNING(
                'GOOGLE_CLIENT_ID hoặc GOOGLE_CLIENT_SECRET chưa set — bỏ qua Google OAuth.'
            ))
            return

        from allauth.socialaccount.models import SocialApp

        app, created = SocialApp.objects.update_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': client_id,
                'secret': client_secret,
            }
        )

        # Ensure the SocialApp is linked to the current Site
        site = Site.objects.get_current()
        if not app.sites.filter(pk=site.pk).exists():
            app.sites.add(site)

        verb = 'Tạo mới' if created else 'Cập nhật'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} Google SocialApp (client_id={client_id[:12]}…)'
        ))
