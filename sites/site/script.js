// Simple client‑side form handling
document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('contactForm');
  const messageDiv = document.getElementById('formMessage');

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    // Basic validation (HTML5 already does it, but we add a quick check)
    const name = form.name.value.trim();
    const email = form.email.value.trim();
    const message = form.message.value.trim();

    if (!name || !email || !message) {
      showMessage('Please fill in all fields.', 'error');
      return;
    }

    // Simulate sending data – in a real site you would POST to a server endpoint
    setTimeout(() => {
      showMessage('Thank you! Your message has been sent.', 'success');
      form.reset();
    }, 500);
  });

  function showMessage(text, type) {
    messageDiv.textContent = text;
    messageDiv.style.color = type === 'error' ? '#c00' : '#080';
  }
});