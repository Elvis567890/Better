// Mobile navigation toggle
const navToggle = document.querySelector('.nav-toggle');
const navList = document.querySelector('.nav-list');
navToggle.addEventListener('click', () => {
    navList.classList.toggle('show');
});

// Close mobile menu after clicking a link
navList.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
        navList.classList.remove('show');
    });
});

// Skill bar animation when section enters viewport
const skillSection = document.getElementById('skills');
const skillBars = document.querySelectorAll('.skills .progress div');

function animateSkills() {
    const rect = skillSection.getBoundingClientRect();
    if (rect.top <= window.innerHeight && rect.bottom >= 0) {
        skillBars.forEach(bar => {
            const target = bar.parentElement.parentElement.querySelector('h3').innerText;
            // Map skill name to percentage (hard‑coded for demo)
            const map = {
                'HTML5': '95%',
                'CSS3 / SCSS': '90%',
                'JavaScript': '85%',
                'React': '80%',
                'UI/UX Design': '88%'
            };
            const width = map[target] || '70%';
            bar.style.width = width;
        });
        window.removeEventListener('scroll', animateSkills);
    }
}
window.addEventListener('scroll', animateSkills);
// Trigger once in case the section is already visible on load
animateSkills();

// Simple contact form validation & feedback
const form = document.getElementById('contactForm');
const messageEl = form.querySelector('.form-message');
form.addEventListener('submit', e => {
    e.preventDefault();
    const name = form.name.value.trim();
    const email = form.email.value.trim();
    const message = form.message.value.trim();
    if (!name || !email || !message) {
        messageEl.textContent = 'Please fill in all fields.';
        messageEl.style.color = '#e53935';
        return;
    }
    // Simulate successful submission
    messageEl.textContent = 'Thank you! Your message has been sent.';
    messageEl.style.color = '#4caf50';
    form.reset();
});