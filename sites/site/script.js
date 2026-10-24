document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('signupForm');
    const messageDiv = document.getElementById('message');

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        // Simple client‑side validation
        const name = form.name.value.trim();
        const email = form.email.value.trim();
        const phone = form.phone.value.trim();

        if (!name || !email || !phone) {
            showMessage('Please fill in all fields.', 'error');
            return;
        }
        // Simulate successful submission
        showMessage('Thank you, ' + name + '! Your information has been received.', 'success');
        form.reset();
    });

    function showMessage(msg, type) {
        messageDiv.textContent = msg;
        messageDiv.style.color = type === 'success' ? 'green' : 'red';
    }
});