from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import LoginForm, ProfileForm
from .models import TeacherProfile


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
            
            # Find user by email
            from django.contrib.auth.models import User
            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Chào mừng {user.get_full_name() or user.email}!')
                next_url = request.GET.get('next', '/dashboard/')
                return redirect(next_url)
            else:
                messages.error(request, 'Email hoặc mật khẩu không đúng.')
    
    return render(request, 'accounts/login.html', {'form': form})


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
