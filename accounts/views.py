import logging
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.dispatch import receiver
from allauth.account.signals import user_logged_in
from .forms import LoginForm, RegisterForm, ProfileForm
from .models import TeacherProfile
from .credits import ensure_wallet
from django.utils.http import url_has_allowed_host_and_scheme

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def ensure_teacher_profile(sender, request, user, **kwargs):
    """Auto-create TeacherProfile on any login (including Google OAuth)."""
    TeacherProfile.objects.get_or_create(user=user)


def login_view(request):
    """Login page — email/password only, no registration."""
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    
    form = LoginForm()
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            from django.contrib.auth.models import User
            user_obj = User.objects.filter(email__iexact=email).first()
            user = authenticate(request, username=user_obj.username if user_obj else email, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, 'Đăng nhập thành công.')
                next_url = safe_next_url(request)
                return redirect(next_url)
            else:
                messages.error(request, 'Email hoặc mật khẩu không đúng.')
    
    return render(request, 'accounts/login.html', {'form': form})


def register_view(request):
    """Registration page — email/password, or via Google."""
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    form = RegisterForm()

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            full_name = form.cleaned_data['full_name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            from .registration import start_signup
            from django.core.exceptions import ValidationError
            parts = full_name.strip().split()
            try:
                start_signup(request, {'email': email, 'password': password,
                    'first_name': ' '.join(parts[:-1]) if len(parts) > 1 else parts[0],
                    'last_name': parts[-1] if len(parts) > 1 else ''},
                    request.POST.get('cf-turnstile-response', ''))
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'Nếu email có thể đăng ký, liên kết xác minh đã được gửi. Vui lòng kiểm tra hộp thư để hoàn tất đăng ký.')
                return redirect('accounts:login')

    from .registration import signup_ready
    from django.conf import settings
    return render(request, 'accounts/register.html', {
        'form': form, 'signup_ready': signup_ready(), 'turnstile_site_key': settings.TURNSTILE_SITE_KEY,
    })



def logout_view(request):
    """Logout and redirect to login page."""
    if request.method == 'POST':
        logout(request)
        messages.success(request, 'Đã đăng xuất thành công.')
    return redirect('accounts:login')


@login_required
def profile_view(request):
    """Teacher profile page."""
    profile, created = TeacherProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            # Update User model fields
            request.user.first_name = form.cleaned_data['first_name']
            request.user.last_name = form.cleaned_data['last_name']
            request.user.save()
            
            form.save()
            messages.success(request, 'Hồ sơ đã được cập nhật.')
            
            if request.htmx:
                return render(request, 'partials/_toast.html')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(
            instance=profile,
            initial={
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
            }
        )
    
    return render(request, 'accounts/profile.html', {
        'form': form,
        'profile': profile,
    })


def safe_next_url(request):
    target = request.GET.get('next', '/dashboard/')
    return target if url_has_allowed_host_and_scheme(target, {request.get_host()}, require_https=request.is_secure()) else '/dashboard/'


@login_required
def credits_view(request):
    wallet = ensure_wallet(request.user)
    return render(request, 'accounts/credits.html', {
        'wallet': wallet, 'entries': wallet.entries.select_related('actor')[:50],
    })
