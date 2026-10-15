document.addEventListener('DOMContentLoaded',()=>{
  const toggle=document.querySelector('.menu-toggle');
  const nav=document.querySelector('.nav-links');
  toggle.addEventListener('click',()=>{nav.classList.toggle('show');});
  document.querySelectorAll('a[href^="#"]').forEach(anchor=>{
    anchor.addEventListener('click',e=>{
      e.preventDefault();
      document.querySelector(anchor.getAttribute('href')).scrollIntoView({behavior:'smooth'});
      if(nav.classList.contains('show')) nav.classList.remove('show');
    });
  });
  const form=document.getElementById('contactForm');
  const msg=document.getElementById('formMessage');
  form.addEventListener('submit',e=>{
    e.preventDefault();
    msg.textContent='Thank you! Your message has been sent.';
    msg.style.color='green';
    form.reset();
  });
});