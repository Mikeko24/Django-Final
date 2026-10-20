import './map.js';

(() => {
    const dialog = document.getElementById('need-update-dialog');
    const content = document.getElementById('need-update-dialog-content');

    if (!dialog || !content) {
        return;
    }

    const closeDialog = () => {
        window.destroyCommunityLocationPicker(content);
        dialog.close();
        document.body.classList.remove('need-update-open');
        content.replaceChildren();
    };

    const showLoadError = (link) => {
        content.replaceChildren();
        const panel = document.createElement('section');
        panel.className = 'need-update-error';
        panel.setAttribute('role', 'alert');

        const icon = document.createElement('span');
        icon.className = 'need-update-error-mark';
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = '!';

        const message = document.createElement('div');
        const title = document.createElement('h2');
        title.textContent = 'Could not load the update form';
        const detail = document.createElement('p');
        detail.textContent = 'The app server did not respond. Make sure Django is running, then try again.';
        const actions = document.createElement('div');
        actions.className = 'need-update-error-actions';
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.className = 'button';
        retry.textContent = 'Try again';
        retry.addEventListener('click', () => loadUpdateForm(link));
        actions.append(retry);
        message.append(title, detail, actions);
        panel.append(icon, message);
        content.append(panel);
    };

    const initializeDialog = () => {
        const locationMap = content.querySelector('#location-picker-map');
        if (locationMap) {
            window.initializeCommunityLocationPicker(content);
        }

        content.querySelectorAll('[data-close-need-update]').forEach((button) => {
            button.addEventListener('click', closeDialog);
        });

        const form = content.querySelector('[data-need-update-form]');
        if (form) {
            form.addEventListener('submit', submitForm);
        }
    };

    const submitForm = async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const submitButton = form.querySelector('[data-need-update-submit]');
        submitButton.disabled = true;

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

            if (!response.ok && response.status !== 422) {
                throw new Error(`The update could not be saved (HTTP ${response.status}).`);
            }

            window.destroyCommunityLocationPicker(content);
            content.innerHTML = await response.text();
            initializeDialog();
            dialog.querySelector('[data-need-update-submit]')?.focus();
        } catch (error) {
            const requestError = content.querySelector('[data-need-update-request-error]');
            if (requestError) {
                requestError.textContent = 'The app server did not respond. Check that Django is running, then try saving again.';
                requestError.hidden = false;
            }
            const currentSubmitButton = content.querySelector('[data-need-update-submit]');
            if (currentSubmitButton) {
                currentSubmitButton.disabled = false;
            }
        }
    };

    const loadUpdateForm = async (link) => {
        content.textContent = 'Loading need details…';
        if (!dialog.open) {
            dialog.showModal();
            document.body.classList.add('need-update-open');
        }

        try {
            const response = await fetch(link.href, {
                headers: {'X-Modal-Request': 'true'},
                credentials: 'same-origin',
            });
            if (!response.ok) {
                throw new Error(`The update form could not be loaded (HTTP ${response.status}).`);
            }
            content.innerHTML = await response.text();
            initializeDialog();
            dialog.querySelector('[data-need-update-title]')?.focus();
        } catch {
            showLoadError(link);
        }
    };

    document.querySelectorAll('[data-need-update]').forEach((link) => {
        link.addEventListener('click', async (event) => {
            event.preventDefault();
            await loadUpdateForm(link);
        });
    });

    dialog.addEventListener('click', (event) => {
        if (event.target === dialog) {
            closeDialog();
        }
    });
    dialog.addEventListener('cancel', (event) => {
        event.preventDefault();
        closeDialog();
    });
    dialog.addEventListener('close', () => {
        document.body.classList.remove('need-update-open');
    });
})();
