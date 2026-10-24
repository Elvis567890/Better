document.addEventListener('DOMContentLoaded', function () {
  const navToggle = document.getElementById('navToggle');
  const nav = document.getElementById('nav');

  navToggle.addEventListener('click', function () {
    nav.querySelector('ul').classList.toggle('show');
  });

  const form = document.getElementById('contactForm');
  const formMessage = document.getElementById('formMessage');

  form.addEventListener('submit', function (e) {
    e.preventDefault();

    // Simple validation
    const name = form.name.value.trim();
    const email = form.email.value.trim();
    const service = form.service.value;

    if (!name || !email || !service) {
      formMessage.textContent = 'Please fill in all required fields.';
      formMessage.style.color = 'red';
      return;
    }

    // Simulate successful submission
    formMessage.textContent = 'Thank you! Your request has been sent.';
    formMessage.style.color = 'green';
    form.reset();
  });
});