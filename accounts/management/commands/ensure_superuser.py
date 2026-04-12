"""
Tự động tạo superuser nếu chưa có — dùng cho Railway deploy.
Đọc từ biến môi trường: DJANGO_SU_EMAIL, DJANGO_SU_PASSWORD
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Tạo superuser từ biến môi trường nếu chưa tồn tại'

    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_SU_EMAIL')
        password = os.environ.get('DJANGO_SU_PASSWORD')
        username = os.environ.get('DJANGO_SU_USERNAME', 'admin')

        if not email or not password:
            self.stdout.write(self.style.WARNING(
                'DJANGO_SU_EMAIL hoặc DJANGO_SU_PASSWORD chưa set — bỏ qua.'
            ))
            return

        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f'Superuser "{user.username}" đã tồn tại — password đã reset.'
            ))
        else:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
            )
            self.stdout.write(self.style.SUCCESS(
                f'Superuser "{username}" ({email}) đã được tạo.'
            ))

        # Đảm bảo allauth EmailAddress record
        try:
            from allauth.account.models import EmailAddress
            EmailAddress.objects.get_or_create(
                user=user, email=email,
                defaults={'verified': True, 'primary': True}
            )
        except Exception:
            pass
