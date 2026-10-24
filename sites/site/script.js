document.addEventListener('DOMContentLoaded', () => {
  // Mobile navigation toggle
  const toggleBtn = document.querySelector('.nav-toggle');
  const navList = document.querySelector('nav ul');
  toggleBtn.addEventListener('click', () => {
    navList.classList.toggle('show');
  });

  // Simple contact form feedback
  const form = document.getElementById('contactForm');
  const messageEl = document.getElementById('formMessage');
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    // In a real site you would send the data via fetch/AJAX.
    messageEl.textContent = 'Thank you, your message has been sent.';
    form.reset();
  });
});