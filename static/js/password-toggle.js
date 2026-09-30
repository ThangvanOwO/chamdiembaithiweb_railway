document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('input[type="password"]').forEach(function (input) {
        if (!input.id || input.parentElement.classList.contains('password-field')) return;
        const field = document.createElement('div');
        field.className = 'password-field';
        input.before(field);
        field.appendChild(input);
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'password-toggle';
        button.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/><path class="password-eye-slash" d="m4 4 16 16"/></svg>';
        button.setAttribute('aria-label', 'Hiện mật khẩu');
        button.title = 'Hiện mật khẩu';
        button.setAttribute('aria-controls', input.id);
        button.setAttribute('aria-pressed', 'false');
        button.addEventListener('click', function () {
            const visible = input.type === 'password';
            input.type = visible ? 'text' : 'password';
            button.setAttribute('aria-label', visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
            button.title = visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu';
            button.setAttribute('aria-pressed', String(visible));
        });
        field.appendChild(button);
    });
});
