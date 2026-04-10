from django import forms
from django.contrib.auth.models import User
from .models import TeacherProfile


class LoginForm(forms.Form):
    """Login form — email/password only."""
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'email@truonghoc.edu.vn',
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
        fields = ['school', 'subject', 'phone']
        widgets = {
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
