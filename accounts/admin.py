from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django import forms
from .models import TeacherProfile
from .models import CreditWallet, CreditEntry, ScanOperation
from .credits import adjust_credits
from .credits import CreditError
from django.contrib import messages
from django.shortcuts import redirect
import uuid

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

    # Staff credit operators must not grant themselves permissions or reset an admin password.
    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

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

from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin


class RestrictedGroupAdmin(GroupAdmin):
    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


admin.site.unregister(Group)
admin.site.register(Group, RestrictedGroupAdmin)

# Customize admin site
admin.site.site_header = 'GradeFlow — Quản trị hệ thống'
admin.site.site_title = 'GradeFlow Admin'
admin.site.index_title = 'Quản lý hệ thống chấm điểm'


class WalletAdjustmentForm(forms.ModelForm):
    adjustment = forms.IntegerField(label='Cộng / trừ điểm', initial=0,
                                    help_text='Số dương để cộng, số âm để trừ.')
    reason = forms.CharField(label='Lý do điều chỉnh', required=False, max_length=255)
    reference = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)

    class Meta:
        model = CreditWallet
        fields = ()

    def clean(self):
        data = super().clean()
        amount = data.get('adjustment', 0)
        if amount and not data.get('reason', '').strip():
            self.add_error('reason', 'Cần ghi lý do điều chỉnh.')
        if amount < 0 and self.instance.balance + amount < 0:
            self.add_error('adjustment', 'Không đủ điểm để trừ.')
        return data


@admin.register(CreditWallet)
class CreditWalletAdmin(admin.ModelAdmin):
    form = WalletAdjustmentForm
    list_display = ('user', 'balance')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('user', 'balance')
    fields = ('user', 'balance', 'adjustment', 'reason', 'reference')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        amount = form.cleaned_data['adjustment']
        if amount:
            adjust_credits(obj.pk, amount, form.cleaned_data['reason'], request.user,
                           f'admin:{form.cleaned_data["reference"]}')

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except CreditError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return redirect(request.path)


class ReadOnlyCreditAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CreditEntry)
class CreditEntryAdmin(ReadOnlyCreditAdmin):
    list_display = ('created_at', 'wallet', 'amount', 'balance_after', 'reason', 'actor')
    search_fields = ('wallet__user__email', 'reference', 'reason')
    list_select_related = ('wallet__user', 'actor')


@admin.register(ScanOperation)
class ScanOperationAdmin(ReadOnlyCreditAdmin):
    list_display = ('id', 'wallet', 'reserved', 'charged', 'finished', 'created_at')
    list_filter = ('finished',)
    exclude = ('response_body',)
    search_fields = ('wallet__user__email', 'key')


from .models import ModerationEvent


@admin.register(ModerationEvent)
class ModerationEventAdmin(ReadOnlyCreditAdmin):
    list_display = ('created_at', 'user', 'action_label', 'actor', 'reason')
    list_filter = ('action',)
    search_fields = ('user__email', 'actor__email', 'reason')
    list_select_related = ('user', 'actor')

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_module_permission(self, request):
        return request.user.is_superuser
