// Preserve a key across resubmissions of this form, renew on a fresh page load.
document.querySelectorAll('form[data-scan-form]').forEach(function (form) {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'scan_key';
    input.value = crypto.randomUUID();
    form.appendChild(input);
});
