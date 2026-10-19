// Mobile navigation toggle
const navToggle = document.querySelector('.nav-toggle');
const navMenu = document.querySelector('.nav ul');

navToggle.addEventListener('click', () => {
  navMenu.classList.toggle('show');
});

// Simple form handling (no backend)
const form = document.getElementById('contactForm');
const formMessage = document.getElementById('formMessage');

form.addEventListener('submit', function (e) {
  e.preventDefault();
  // Basic validation (HTML5 already does it, but we add a friendly message)
  const name = form.name.value.trim();
  const email = form.email.value.trim();
  const message = form.message.value.trim();

  if (name && email && message) {
    // Simulate successful submission
    formMessage.textContent = 'Thank you, ' + name + '! Your message has been sent.';
    formMessage.style.color = '#27ae60';
    form.reset();
  } else {
    formMessage.textContent = 'Please fill in all fields.';
    formMessage.style.color = '#e74c3c';
  }
});
