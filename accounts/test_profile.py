from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import TeacherProfile


class ProfileAvatarTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = User.objects.create_user('profile-test', 'profile@example.com', 'Example249!')
        self.other = User.objects.create_user('other-profile', 'other@example.com', 'Example249!')
        self.profile = TeacherProfile.objects.create(user=self.user)
        self.other_profile = TeacherProfile.objects.create(user=self.other)
        self.client.force_login(self.user)
        self.data = {'first_name': 'Nguyễn', 'last_name': 'An', 'school': 'Trường A', 'subject': 'Toán', 'phone': ''}

    def image(self, format='PNG', size=(800, 600)):
        output = BytesIO()
        Image.new('RGB', size, '#0f766e').save(output, format=format)
        return SimpleUploadedFile('avatar.' + format.lower(), output.getvalue(), content_type='image/' + format.lower())

    def test_upload_normalizes_image_and_only_updates_current_user(self):
        response = self.client.post(reverse('accounts:profile'), {**self.data, 'avatar': self.image(), 'user': self.other.pk}, follow=True)
        self.assertContains(response, 'Hồ sơ đã được cập nhật.')
        self.profile.refresh_from_db()
        self.other_profile.refresh_from_db()
        self.assertFalse(self.other_profile.avatar)
        with Image.open(self.profile.avatar.path) as image:
            self.assertEqual(image.size, (512, 512))
            self.assertEqual(image.format, 'JPEG')
        self.assertContains(response, self.profile.avatar.url, count=3)
        old_name = self.profile.avatar.name
        self.client.post(reverse('accounts:profile'), self.data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar.name, old_name)

    def test_invalid_image_leaves_profile_unchanged(self):
        invalid = SimpleUploadedFile('avatar.png', b'not an image', content_type='image/png')
        response = self.client.post(reverse('accounts:profile'), {**self.data, 'avatar': invalid})
        self.assertEqual(response.status_code, 200)
        self.assertIn('avatar', response.context['form'].errors)
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertFalse(self.profile.avatar)
        self.assertEqual(self.user.first_name, '')

    def test_unsupported_or_oversized_image_rejected(self):
        for upload in [self.image('GIF'), SimpleUploadedFile('large.png', self.image().read() + b'0' * (5*1024*1024), content_type='image/png')]:
            response = self.client.post(reverse('accounts:profile'), {**self.data, 'avatar': upload})
            self.assertIn('avatar', response.context['form'].errors)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.avatar)

    def test_anonymous_upload_requires_login(self):
        self.client.logout()
        response = self.client.post(reverse('accounts:profile'), {**self.data, 'avatar': self.image()})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
