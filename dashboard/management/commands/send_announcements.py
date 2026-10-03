import time
from django.core.management.base import BaseCommand
from dashboard.announcements import dispatch_pending, firebase_status


class Command(BaseCommand):
    requires_system_checks = []  # Avoid importing grading URLs/OpenCV in the idle sender.
    help = 'Gửi thông báo Firebase từ hàng đợi, độc lập với tiến trình chấm bài.'

    def add_arguments(self, parser):
        parser.add_argument('--watch', action='store_true')

    def handle(self, *args, **options):
        while True:
            if not firebase_status():
                self.stdout.write('Firebase chưa được cấu hình đúng dự án.')
            else:
                count = dispatch_pending()
                if count:
                    self.stdout.write(f'Firebase đã nhận {count} thông báo.')
            if not options['watch']:
                return
            time.sleep(10)
