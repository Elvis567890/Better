// Earnings calculator
document.addEventListener('DOMContentLoaded', function () {
    const btn = document.getElementById('calcBtn');
    const resultEl = document.getElementById('calcResult');
    btn.addEventListener('click', function () {
        const hours = parseFloat(document.getElementById('hours').value) || 0;
        const rate = parseFloat(document.getElementById('rate').value) || 0;
        const weekly = hours * rate;
        const monthly = weekly * 4;
        resultEl.textContent = `≈ $${weekly.toFixed(2)} per week | $${monthly.toFixed(2)} per month`;
    });

    // Simple contact form handler (demo only)
    const form = document.getElementById('contactForm');
    form.addEventListener('submit', function (e) {
        e.preventDefault();
        alert('Thank you! Your message has been received. I will reply via email or WhatsApp soon.');
        form.reset();
    });
});