// Navigation handling
document.querySelectorAll('nav a').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    const page = link.getAttribute('data-page');
    document.querySelectorAll('.page').forEach(sec => {
      sec.classList.toggle('active', sec.id === page);
    });
    // Optional: highlight active link
    document.querySelectorAll('nav a').forEach(l => l.classList.toggle('active', l === link));
  });
});

// Set current year in footer
document.getElementById('year').textContent = new Date().getFullYear();

// Simple form handling
const form = document.getElementById('contactForm');
const msgDiv = document.getElementById('formMessage');
form.addEventListener('submit', e => {
  e.preventDefault();
  // In a real site you'd send data to a server. Here we just show a thank‑you message.
  msgDiv.textContent = 'Thank you for your message!';
  form.reset();
});