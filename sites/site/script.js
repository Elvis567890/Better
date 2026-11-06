// Mobile navigation toggle
document.addEventListener('DOMContentLoaded', function () {
  const toggleBtn = document.querySelector('.nav-toggle');
  const navList = document.querySelector('nav ul');

  toggleBtn.addEventListener('click', function () {
    navList.classList.toggle('show');
  });

  // Close menu after clicking a link (optional, improves UX on mobile)
  navList.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      navList.classList.remove('show');
    });
  });
});