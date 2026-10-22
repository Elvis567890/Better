document.addEventListener('DOMContentLoaded',function(){
  const modal=document.getElementById('modal');
  const openBtn=document.getElementById('ctaBtn');
  const closeBtn=document.getElementById('closeModal');
  const form=document.getElementById('auditForm');

  openBtn.addEventListener('click',()=>{modal.classList.remove('hidden');});
  closeBtn.addEventListener('click',()=>{modal.classList.add('hidden');});
  window.addEventListener('click',e=>{if(e.target===modal){modal.classList.add('hidden');}});
  form.addEventListener('submit',e=>{
    e.preventDefault();
    const name=document.getElementById('name').value.trim();
    const email=document.getElementById('email').value.trim();
    const url=document.getElementById('url').value.trim();
    if(name && email && url){
      alert('Thank you, '+name+'! Your free audit request has been received.');
      form.reset();
      modal.classList.add('hidden');
    }else{
      alert('Please fill in all fields.');
    }
  });
});
