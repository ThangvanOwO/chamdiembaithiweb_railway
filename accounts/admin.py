from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django import forms
from .models import TeacherProfile

# =============================================================================
# 1. Ẩn các app không cần thiết khỏi admin
# =============================================================================

# Ẩn "Sites" — không có chức năng gì cho app này
admin.site.unregister(Site)

# Ẩn "Email addresses" của allauth
try:
    from allauth.account.models import EmailAddress
    admin.site.unregister(EmailAddress)
except (admin.sites.NotRegistered, ImportError):
    pass


# =============================================================================
# 2. Custom User Creation Form — Dùng Email thay vì Username
# =============================================================================

class EmailUserCreationForm(forms.ModelForm):
    """Form tạo user mới: email làm trường chính, tự tạo username từ email."""
    email = forms.EmailField(
        label='Địa chỉ Email',
        help_text='Đây là tài khoản giáo viên sẽ dùng để đăng nhập.',
        widget=forms.EmailInput(attrs={'autofocus': True}),
    )
    first_name = forms.CharField(label='Họ', max_length=150, required=False)
    last_name = forms.CharField(label='Tên', max_length=150, required=False)
    password1 = forms.CharField(
        label='Mật khẩu',
        widget=forms.PasswordInput,
        help_text='Tối thiểu 8 ký tự.',
    )
    password2 = forms.CharField(
        label='Xác nhận mật khẩu',
        widget=forms.PasswordInput,
        help_text='Nhập lại mật khẩu để xác nhận.',
    )

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email này đã được sử dụng.')
        return email

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Mật khẩu không khớp.')
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        # Tạo username tự động từ phần trước @ của email
        email = self.cleaned_data['email']
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        user.username = username
        user.email = email
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


# =============================================================================
# 3. Custom UserAdmin — Email-centric
# =============================================================================

class TeacherProfileInline(admin.StackedInline):
    model = TeacherProfile
    can_delete = False
    verbose_name = 'Hồ sơ giáo viên'
    verbose_name_plural = 'Hồ sơ giáo viên'
    fields = ('school', 'subject', 'phone', 'avatar')


class UserAdmin(BaseUserAdmin):
    inlines = (TeacherProfileInline,)
    add_form = EmailUserCreationForm

    # Danh sách user — hiện email thay vì username
    list_display = ('email', 'first_name', 'last_name', 'get_school', 'is_active', 'date_joined')
    list_filter = ('is_active', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)

    # Form thêm user mới — chỉ hiện email + password
    add_fieldsets = (
        ('Thông tin đăng nhập', {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
        ('Thông tin cá nhân', {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name'),
        }),
    )

    # Form chỉnh sửa user — ẩn username, hiện email trước
    fieldsets = (
        ('Tài khoản', {'fields': ('email', 'password')}),
        ('Thông tin cá nhân', {'fields': ('first_name', 'last_name')}),
        ('Phân quyền', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        ('Ngày quan trọng', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )

    def get_school(self, obj):
        try:
            return obj.teacher_profile.school
        except TeacherProfile.DoesNotExist:
            return '—'
    get_school.short_description = 'Trường'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Auto-create TeacherProfile when admin creates a user
        TeacherProfile.objects.get_or_create(user=obj)


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Customize admin site
admin.site.site_header = 'GradeFlow — Quản trị hệ thống'
admin.site.site_title = 'GradeFlow Admin'
admin.site.index_title = 'Quản lý hệ thống chấm điểm'
