from django.db import models
from django.contrib.auth.models import User


class TeacherProfile(models.Model):
    """Extended profile for teachers. Account created by Admin only."""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    school = models.CharField('Trường', max_length=200, blank=True, default='')
    subject = models.CharField('Môn dạy', max_length=100, blank=True, default='')
    phone = models.CharField('Số điện thoại', max_length=20, blank=True, default='')
    avatar = models.ImageField('Ảnh đại diện', upload_to='avatars/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Hồ sơ giáo viên'
        verbose_name_plural = 'Hồ sơ giáo viên'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} — {self.school}"
    
    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.email
    
    @property
    def initials(self):
        name = self.user.get_full_name()
        if name:
            parts = name.split()
            return ''.join([p[0].upper() for p in parts[:2]])
        return self.user.email[0].upper()
