/**
 * GradeFlow — Micro-interactions & Polished JS
 * Ink ripple, count-up, dark mode, page loader, mobile menu
 */

(function () {
    'use strict';

    /* =========================================================================
       1. INK RIPPLE — on all .btn elements
       ========================================================================= */

    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn');
        if (!btn) return;

        const rect = btn.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const size = Math.max(rect.width, rect.height) * 2;

        const ripple = document.createElement('span');
        ripple.classList.add('ripple');
        ripple.style.width = ripple.style.height = size + 'px';
        ripple.style.left = x - size / 2 + 'px';
        ripple.style.top = y - size / 2 + 'px';

        btn.appendChild(ripple);
        ripple.addEventListener('animationend', function () {
            ripple.remove();
        });
    });


    /* =========================================================================
       2. COUNT-UP ANIMATION — on .stat-value elements
       via IntersectionObserver (animate once on viewport enter)
       ========================================================================= */

    function animateCountUp(el) {
        const text = el.textContent.trim();
        // Only animate numeric values
        const match = text.match(/^([\d.]+)(%?)$/);
        if (!match) return;

        const target = parseFloat(match[1]);
        const suffix = match[2] || '';
        const isDecimal = text.includes('.');
        const duration = 800;
        const start = performance.now();

        el.textContent = '0' + suffix;

        function step(now) {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            // Ease-out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = target * eased;

            el.textContent = (isDecimal ? current.toFixed(1) : Math.round(current)) + suffix;

            if (progress < 1) {
                requestAnimationFrame(step);
            }
        }

        requestAnimationFrame(step);
    }

    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    animateCountUp(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.3 });

        document.querySelectorAll('.stat-value').forEach(function (el) {
            observer.observe(el);
        });
    }


    /* =========================================================================
       3. DARK MODE TOGGLE
       ========================================================================= */

    const THEME_KEY = 'gradeflow-theme';

    function getPreferredTheme() {
        const stored = localStorage.getItem(THEME_KEY);
        if (stored) return stored;
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(THEME_KEY, theme);

        // Update toggle icon
        const toggleIcon = document.getElementById('theme-toggle-icon');
        if (toggleIcon) {
            toggleIcon.innerHTML = theme === 'dark'
                ? '<path d="M10 3a7 7 0 107 7 5 5 0 01-7-7z" stroke="currentColor" stroke-width="1.5" fill="none"/>'
                : '<circle cx="10" cy="10" r="4" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.93 4.93l1.41 1.41M13.66 13.66l1.41 1.41M4.93 15.07l1.41-1.41M13.66 6.34l1.41-1.41" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>';
        }
    }

    // Apply on load
    setTheme(getPreferredTheme());

    // Expose toggle function for Alpine
    window.toggleTheme = function () {
        const current = document.documentElement.getAttribute('data-theme');
        setTheme(current === 'dark' ? 'light' : 'dark');
    };


    /* =========================================================================
       4. PAGE LOADER — Thin top progress bar
       ========================================================================= */

    var loader = document.getElementById('page-loader');

    if (loader) {
        // HTMX events
        document.body.addEventListener('htmx:beforeRequest', function () {
            loader.className = 'loading';
        });

        document.body.addEventListener('htmx:afterRequest', function () {
            loader.className = 'done';
            setTimeout(function () {
                loader.className = '';
            }, 600);
        });
    }


    /* =========================================================================
       5. MOBILE SIDEBAR — Toggle with backdrop
       ========================================================================= */

    window.toggleMobileMenu = function () {
        var sidebar = document.querySelector('.sidebar');
        var backdrop = document.querySelector('.sidebar-backdrop');

        if (!sidebar) return;

        var isOpen = sidebar.classList.contains('mobile-open');

        if (isOpen) {
            sidebar.classList.remove('mobile-open');
            if (backdrop) backdrop.classList.remove('active');
            document.body.style.overflow = '';
        } else {
            sidebar.classList.add('mobile-open');
            if (backdrop) backdrop.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    };

    // Close on backdrop click
    document.addEventListener('click', function (e) {
        if (e.target.classList.contains('sidebar-backdrop')) {
            window.toggleMobileMenu();
        }
    });

    // Close on Escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            var sidebar = document.querySelector('.sidebar.mobile-open');
            if (sidebar) window.toggleMobileMenu();
        }
    });


    /* =========================================================================
       6. KEYBOARD SHORTCUT — Ctrl/Cmd + K to focus search (if present)
       ========================================================================= */

    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            var search = document.getElementById('history-search');
            if (search) search.focus();
        }
    });


    /* =========================================================================
       7. AUTO-HIDE NAVBAR on scroll (subtle 64px hide)
       ========================================================================= */

    var lastScrollY = 0;
    var navbar = document.querySelector('.top-navbar');

    if (navbar) {
        window.addEventListener('scroll', function () {
            var currentScrollY = window.scrollY;
            if (currentScrollY > 120 && currentScrollY > lastScrollY) {
                navbar.style.transform = 'translateY(-100%)';
            } else {
                navbar.style.transform = 'translateY(0)';
            }
            lastScrollY = currentScrollY;
        }, { passive: true });

        navbar.style.transition = 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)';
    }

})();
