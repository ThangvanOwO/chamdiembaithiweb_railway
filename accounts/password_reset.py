from django.conf import settings
from django.contrib.auth.views import PasswordResetView
from smtplib import SMTPException


class ConfiguredPasswordResetView(PasswordResetView):
    def form_valid(self, form):
        if not settings.EMAIL_HOST:
            form.add_error(None, 'Email khôi phục chưa được cấu hình. Vui lòng liên hệ quản trị viên để đặt lại mật khẩu.')
            return self.form_invalid(form)
        try:
            return super().form_valid(form)
        except (SMTPException, OSError):
            form.add_error(None, 'Chưa gửi được email. Vui lòng thử lại sau hoặc liên hệ quản trị viên.')
            return self.form_invalid(form)
