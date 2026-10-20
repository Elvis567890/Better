// Smooth scroll for internal links
document.addEventListener('DOMContentLoaded', function() {
  const links = document.querySelectorAll('a.scroll');
  links.forEach(link => {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      const targetId = this.getAttribute('href').substring(1);
      const target = document.getElementById(targetId);
      if (target) {
        window.scrollTo({
          top: target.offsetTop - 20,
          behavior: 'smooth'
        });
      }
    });
  });
});