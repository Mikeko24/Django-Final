(() => {
    const root = document.documentElement;
    const topbar = document.querySelector('.topbar');
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    root.classList.add('ui-ready');

    if (topbar) {
        const updateTopbar = () => topbar.classList.toggle('is-scrolled', window.scrollY > 8);
        updateTopbar();
        window.addEventListener('scroll', updateTopbar, { passive: true });
    }

    document.querySelectorAll('.notice-dismiss').forEach((button) => {
        button.addEventListener('click', () => {
            const notice = button.closest('.notice');
            if (!notice) return;
            if (reduceMotion) {
                notice.remove();
                return;
            }
            notice.classList.add('is-leaving');
            notice.addEventListener('animationend', () => notice.remove(), { once: true });
        });
    });

    if (!reduceMotion && window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
        document.querySelectorAll('.stat-card, .admin-grid .panel, .columns .panel').forEach((surface) => {
            surface.addEventListener('pointermove', (event) => {
                const bounds = surface.getBoundingClientRect();
                surface.style.setProperty('--pointer-x', `${event.clientX - bounds.left}px`);
                surface.style.setProperty('--pointer-y', `${event.clientY - bounds.top}px`);
            });
        });
    }

    document.querySelectorAll('form').forEach((form) => {
        form.addEventListener('submit', () => {
            const submit = form.querySelector('button[type="submit"]');
            if (!submit) return;
            form.setAttribute('aria-busy', 'true');
            submit.classList.add('is-loading');
        });
    });
})();
