// Simple form handling – shows a thank‑you message without page reload
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('contactForm');
    const messageEl = document.getElementById('formMessage');

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        // In a real site you would send the data via fetch/AJAX.
        const name = form.elements['name'].value.trim();
        messageEl.textContent = `Thank you, ${name}! Your message has been received.`;
        messageEl.classList.remove('hidden');
        form.reset();
    });

    // Optional: smooth scroll for internal links (modern browsers support CSS scroll-behavior, but we add JS fallback)
    const links = document.querySelectorAll('a[href^="#"]');
    links.forEach(link => {
        link.addEventListener('click', function (e) {
            const targetId = this.getAttribute('href').substring(1);
            const target = document.getElementById(targetId);
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
});