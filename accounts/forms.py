from django import forms
from django.contrib.auth.models import User
from .models import TeacherProfile
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator


class LoginForm(forms.Form):
    """Keep the email field name compatible; also accept a username."""
    email = forms.CharField(
        label='Tên tài khoản hoặc email',
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'nguyenvanan hoặc email@truonghoc.edu.vn',
            'autocomplete': 'username',
            'autofocus': True,
            'id': 'login-email',
        })
    )
    password = forms.CharField(
        label='Mật khẩu',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '••••••••',
            'id': 'login-password',
        })
    )


class RegisterForm(forms.Form):
    """Registration form — name, email, password."""
    full_name = forms.CharField(
        label='Họ và tên',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Nguyễn Văn An',
            'id': 'reg-name',
            'autofocus': True,
        })
    )
    email = forms.EmailField(
        label='Email',
        max_length=150,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'email@truonghoc.edu.vn',
            'id': 'reg-email',
        })
    )
    password = forms.CharField(
        label='Mật khẩu',
        min_length=8,
        max_length=128,
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '••••••••',
            'id': 'reg-password',
        })
    )
    password_confirm = forms.CharField(
        label='Xác nhận mật khẩu',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '••••••••',
            'id': 'reg-password-confirm',
        })
    )

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean_password(self):
        password = self.cleaned_data['password']
        validate_password(password, User(email=self.cleaned_data.get('email', '')))
        return password

    def clean(self):
        cleaned_data = super().clean()
        pw = cleaned_data.get('password')
        pw2 = cleaned_data.get('password_confirm')
        if pw and pw2 and pw != pw2:
            self.add_error('password_confirm', 'Mật khẩu không khớp.')
        return cleaned_data


class UsernameRegisterForm(RegisterForm):
    """A username is not an email identity; never auto-link an OAuth account."""
    email = None
    username = forms.CharField(
        label='Tên tài khoản', min_length=3, max_length=30,
        validators=[RegexValidator(r'^[a-z0-9][a-z0-9._]{2,29}$',
            'Tên tài khoản gồm 3–30 ký tự: chữ không dấu, số, dấu chấm hoặc gạch dưới.')],
        widget=forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'username'}),
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Tên tài khoản đã được sử dụng. Vui lòng chọn tên khác.')
        return username

    def clean_password(self):
        password = self.cleaned_data['password']
        parts = self.cleaned_data.get('full_name', '').split()
        validate_password(password, User(username=self.data.get('username', ''),
            first_name=' '.join(parts[:-1]), last_name=parts[-1] if parts else ''))
        return password

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            raw = data.get('username', '')
            if isinstance(raw, str):
                data['username'] = raw.strip().lower()
        super().__init__(data, *args, **kwargs)


class ProfileForm(forms.ModelForm):
    """Teacher profile edit form."""
    first_name = forms.CharField(
        label='Họ',
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Nguyễn Văn',
        })
    )
    last_name = forms.CharField(
        label='Tên',
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'An',
        })
    )

    class Meta:
        model = TeacherProfile
        fields = ['school', 'subject', 'phone', 'avatar']
        widgets = {
            'avatar': forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp', 'class': 'avatar-file-input'}),
            'school': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Trường THPT ABC',
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Toán, Lý, Hóa...',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '0901234567',
            }),
        }
        labels = {
            'school': 'Trường',
            'subject': 'Môn dạy',
            'phone': 'Số điện thoại',
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if not avatar or not hasattr(avatar, 'content_type'):
            return avatar
        if avatar.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Ảnh đại diện tối đa 5 MB.')
        from PIL import Image, ImageOps
        from django.core.files.base import ContentFile
        from io import BytesIO
        from uuid import uuid4
        try:
            avatar.seek(0)
            with Image.open(avatar) as original:
                if original.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise forms.ValidationError('Vui lòng chọn ảnh JPG, PNG hoặc WebP.')
                if original.width * original.height > 20_000_000:
                    raise forms.ValidationError('Ảnh quá lớn. Vui lòng chọn ảnh dưới 20 megapixel.')
                normalized = ImageOps.exif_transpose(original).convert('RGB')
                normalized = ImageOps.fit(normalized, (512, 512))
                output = BytesIO()
                normalized.save(output, format='JPEG', quality=88)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise forms.ValidationError('Không thể đọc ảnh. Vui lòng chọn ảnh khác.') from exc
        return ContentFile(output.getvalue(), name=f'{uuid4().hex}.jpg')
