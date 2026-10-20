(() => {
    document.querySelectorAll('[data-close-entry]').forEach((button) => {
        button.addEventListener('click', () => {
            window.parent.postMessage({type: 'entry-modal-close'}, window.location.origin);
        });
    });
})();
