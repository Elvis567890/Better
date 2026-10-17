// Smooth scroll for internal links (fallback for older browsers)
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    const target = document.querySelector(this.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth' });
    }
  });
});

// Simple testimonial slider
const testimonials = document.querySelectorAll('.testimonial');
let current = 0;
function showTestimonial(index) {
  testimonials.forEach((t, i) => {
    t.classList.toggle('active', i === index);
  });
}
function nextTestimonial() {
  current = (current + 1) % testimonials.length;
  showTestimonial(current);
}
// Initialize
if (testimonials.length) {
  showTestimonial(0);
  setInterval(nextTestimonial, 5000);
}

// Simple form handling – just shows an alert (replace with real backend as needed)
const form = document.getElementById('cta-form');
if (form) {
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    const name = this.name.value.trim() || 'Friend';
    alert(`Thank you, ${name}! Your request has been received. I will contact you shortly.`);
    this.reset();
  });
}
