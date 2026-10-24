document.addEventListener('DOMContentLoaded', () => {
  const nav = document.getElementById('nav');
  const toggle = document.getElementById('navToggle');

  // Mobile navigation toggle
  toggle.addEventListener('click', () => {
    nav.classList.toggle('show');
  });

  // Simple contact form handling
  const form = document.getElementById('contactForm');
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    alert('Thank you, your message has been sent!');
    form.reset();
  });
});