(() => {
    const dialog = document.getElementById('entry-dialog');
    const content = document.getElementById('entry-dialog-content');
    let opener = null;

    if (!dialog || !content) return;

    const destroyLocationPicker = () => {
        if (window.destroyCommunityLocationPicker) {
            window.destroyCommunityLocationPicker(content);
        }
    };

    const closeDialog = () => {
        destroyLocationPicker();
        dialog.close();
        document.body.classList.remove('entry-dialog-open');
        content.replaceChildren();
        opener?.focus();
        opener = null;
    };

    const initializeLocationPicker = async () => {
        const mapElement = content.querySelector('#location-picker-map');
        if (!mapElement) return;

        try {
            if (!window.initializeCommunityLocationPicker) {
                await import(new URL('./map.js?v=20261019c', import.meta.url));
            }
            window.initializeCommunityLocationPicker(content);
        } catch {
            const fallback = document.createElement('div');
            fallback.className = 'map-unavailable';
            fallback.setAttribute('role', 'status');
            fallback.textContent = 'The map is temporarily unavailable. You can continue and save this entry without a location pin.';
            mapElement.replaceWith(fallback);
            content.querySelector('#clear-map-location')?.remove();
            const status = content.querySelector('#map-selection-status');
            if (status) status.hidden = true;
        }
    };

    const initializeDialog = async () => {
        content.querySelectorAll('[data-close-entry]').forEach((button) => {
            button.addEventListener('click', closeDialog);
        });
        content.querySelector('[data-entry-form]')?.addEventListener('submit', submitForm);
        await initializeLocationPicker();
        content.querySelector('[data-entry-title]')?.focus();
    };

    const showLoadError = (message) => {
        content.innerHTML = `
            <section class="entry-load-error" role="alert">
                <span class="need-update-error-mark" aria-hidden="true">!</span>
                <div><h2>Could not load this entry form</h2><p>${message}</p>
                <button class="button secondary" type="button" data-close-entry>Close</button></div>
            </section>`;
        content.querySelector('[data-close-entry]')?.addEventListener('click', closeDialog);
    };

    const openFrameEntry = (link) => {
        const frame = document.createElement('iframe');
        const frameUrl = new URL(link.href);
        frameUrl.searchParams.set('modal', 'frame');
        frame.className = 'entry-dialog-frame';
        frame.title = link.textContent.trim() || link.getAttribute('aria-label') || 'Entry form';
        frame.src = frameUrl.href;
        content.replaceChildren(frame);
        frame.addEventListener('load', () => frame.focus(), {once: true});
    };

    const submitForm = async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const submit = form.querySelector('[data-entry-submit]');
        submit.disabled = true;
        submit.classList.add('is-loading');
        form.setAttribute('aria-busy', 'true');

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: {
                    'X-Modal-Request': 'true',
                    'Accept': 'text/html, application/json',
                },
                credentials: 'same-origin',
            });

            if (response.ok && response.headers.get('Content-Type')?.includes('application/json')) {
                closeDialog();
                window.location.reload();
                return;
            }
            if (response.status !== 422) throw new Error(`HTTP ${response.status}`);

            destroyLocationPicker();
            content.innerHTML = await response.text();
            await initializeDialog();
        } catch {
            const requestError = content.querySelector('[data-entry-request-error]');
            if (requestError) {
                requestError.textContent = 'The form could not be saved. Check that the app is running, then try again.';
                requestError.hidden = false;
            }
            const currentSubmit = content.querySelector('[data-entry-submit]');
            if (currentSubmit) {
                currentSubmit.disabled = false;
                currentSubmit.classList.remove('is-loading');
            }
            content.querySelector('[data-entry-form]')?.removeAttribute('aria-busy');
        }
    };

    const openEntry = async (link) => {
        opener = link;
        content.innerHTML = '<div class="entry-loading" role="status"><span></span>Preparing the form…</div>';
        if (!dialog.open) {
            dialog.showModal();
            document.body.classList.add('entry-dialog-open');
        }

        if (typeof window.fetch !== 'function') {
            openFrameEntry(link);
            return;
        }

        try {
            const response = await fetch(link.href, {
                headers: {'X-Modal-Request': 'true'},
                credentials: 'same-origin',
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            content.innerHTML = await response.text();
            await initializeDialog();
        } catch {
            showLoadError('The app server did not respond. Close this window and try again.');
        }
    };

    document.addEventListener('click', (event) => {
        const link = event.target.closest('a[data-entry-modal]');
        if (!link) return;
        event.preventDefault();
        openEntry(link);
    });

    dialog.addEventListener('click', (event) => {
        if (event.target === dialog) closeDialog();
    });
    dialog.addEventListener('cancel', (event) => {
        event.preventDefault();
        closeDialog();
    });
    dialog.addEventListener('close', () => document.body.classList.remove('entry-dialog-open'));
    window.addEventListener('message', (event) => {
        const frame = content.querySelector('iframe');
        if (event.origin !== window.location.origin || event.source !== frame?.contentWindow) return;
        if (event.data?.type === 'entry-modal-close') closeDialog();
        if (event.data?.type === 'entry-modal-saved') {
            closeDialog();
            window.location.reload();
        }
    });
})();
