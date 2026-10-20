// Simple client‑side validation for the contact form
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('contactForm');
    const messageEl = document.getElementById('formMessage');

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        // Clear previous messages
        messageEl.textContent = '';
        messageEl.style.color = '';

        // Gather values
        const name = form.name.value.trim();
        const email = form.email.value.trim();
        const phone = form.phone.value.trim();
        const message = form.message.value.trim();

        // Basic validation
        if (!name || !email || !message) {
            showMessage('Please fill in all required fields.', 'red');
            return;
        }
        if (!validateEmail(email)) {
            showMessage('Please enter a valid email address.', 'red');
            return;
        }

        // Simulate successful submission (replace with real fetch if needed)
        setTimeout(() => {
            showMessage('Thank you! Your message has been sent.', 'green');
            form.reset();
        }, 500);
    });

    function showMessage(msg, color) {
        messageEl.textContent = msg;
        messageEl.style.color = color;
    }

    function validateEmail(email) {
        // Simple email regex
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
});