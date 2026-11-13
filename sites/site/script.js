// Mobile navigation toggle
const navToggle = document.getElementById('nav-toggle');
const nav = document.getElementById('nav');
navToggle.addEventListener('click', () => {
    nav.classList.toggle('show');
});

// Set current year in footer
document.getElementById('year').textContent = new Date().getFullYear();

// Simple form validation & feedback
const form = document.getElementById('booking-form');
const messageEl = document.getElementById('form-message');
form.addEventListener('submit', function (e) {
    e.preventDefault();
    // Basic validation
    const name = form.name.value.trim();
    const email = form.email.value.trim();
    const phone = form.phone.value.trim();
    const date = form.date.value;
    const duration = form.duration.value;
    if (!name || !email || !phone || !date || !duration) {
        messageEl.textContent = 'Please fill in all required fields.';
        messageEl.style.color = '#c00';
        return;
    }
    // Simulate successful submission
    messageEl.textContent = 'Thank you! Your request has been received.';
    messageEl.style.color = '#090';
    form.reset();
});