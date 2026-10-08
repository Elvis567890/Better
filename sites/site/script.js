document.getElementById('contactForm').addEventListener('submit', function(e){
  e.preventDefault();
  const name = this.name.value.trim();
  const email = this.email.value.trim();
  const message = this.message.value.trim();
  const subject = encodeURIComponent('Quick Remote Income Inquiry from ' + name);
  const body = encodeURIComponent('Name: ' + name + '\\nEmail: ' + email + '\\n\\nMessage:\\n' + message);
  const mailtoLink = `mailto:contact@quickremoteincome.com?subject=${subject}&body=${body}`;
  window.location.href = mailtoLink;
  const msgEl = document.getElementById('formMessage');
  msgEl.textContent = 'Opening your email client...';
  msgEl.classList.remove('hidden');
});