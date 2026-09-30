/* Restore the desktop shell before paint; mobile has a separate drawer. */
(function () {
    'use strict';
    let sidebarOpen = true;
    try { sidebarOpen = localStorage.getItem('gradeflow-sidebar') !== 'collapsed'; } catch (_) {}
    document.documentElement.dataset.sidebar = sidebarOpen ? 'expanded' : 'collapsed';
    window.workspaceShell = () => ({
        sidebarOpen, mobileMenuOpen: false, toasts: [],
        init() {
            this.$watch('sidebarOpen', value => {
                document.documentElement.dataset.sidebar = value ? 'expanded' : 'collapsed';
                try { localStorage.setItem('gradeflow-sidebar', value ? 'expanded' : 'collapsed'); } catch (_) {}
            });
        }
    });
    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.sidebar-nav a').forEach(link => {
            if (!link.hasAttribute('aria-label')) link.setAttribute('aria-label', link.textContent.trim());
            link.title = link.getAttribute('aria-label');
        });
        document.addEventListener('click', event => {
            const target = event.target.closest('.nav-item, .sidebar-toggle, .mobile-menu-btn');
            if (!target || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
            const box = target.getBoundingClientRect(), ring = document.createElement('span');
            ring.className = 'water-ring';
            ring.style.left = (event.detail ? event.clientX : box.left + box.width / 2) + 'px';
            ring.style.top = (event.detail ? event.clientY : box.top + box.height / 2) + 'px';
            document.body.appendChild(ring);
            ring.addEventListener('animationend', () => ring.remove(), {once:true});
        });
        const originalToggle = window.toggleTheme;
        if (originalToggle) window.toggleTheme = function () {
            if (!document.startViewTransition || matchMedia('(prefers-reduced-motion: reduce)').matches) { originalToggle(); return; }
            if (window.gradeflowThemeTransition) return;
            const box = document.querySelector('[aria-label="Chuyển giao diện sáng/tối"]').getBoundingClientRect();
            const x = box.left + box.width / 2, y = box.top + box.height / 2;
            const radius = Math.hypot(Math.max(x, innerWidth-x), Math.max(y, innerHeight-y));
            document.documentElement.classList.add('theme-water-transition');
            const transition = document.startViewTransition(originalToggle);
            window.gradeflowThemeTransition = transition;
            transition.ready.then(() => document.documentElement.animate({
                clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`]
            }, {duration:460, easing:'cubic-bezier(.2,.7,.2,1)', pseudoElement:'::view-transition-new(root)'})).catch(() => {});
            transition.finished.finally(() => {
                window.gradeflowThemeTransition = null;
                document.documentElement.classList.remove('theme-water-transition');
            }).catch(() => {});
        };
        const input = document.getElementById('id_avatar'), preview = document.getElementById('avatar-preview');
        if (!input || !preview) return;
        const original = preview.innerHTML;
        let previewUrl;
        input.addEventListener('change', () => {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            const file = input.files[0], status = document.getElementById('avatar-status');
            preview.innerHTML = original;
            if (!file) { status.textContent = ''; return; }
            if (!['image/jpeg','image/png','image/webp'].includes(file.type) || file.size > 5*1024*1024) {
                input.value = ''; status.textContent = 'Chọn ảnh JPG, PNG hoặc WebP, tối đa 5 MB.'; return;
            }
            const img = document.createElement('img');
            img.className = 'avatar-image'; img.alt = 'Ảnh đại diện xem trước';
            previewUrl = URL.createObjectURL(file); img.src = previewUrl;
            preview.replaceChildren(img);
            status.textContent = 'Ảnh mới đã chọn. Bấm Lưu thay đổi để cập nhật.';
        });
    });
})();
