document.getElementById('calcForm').addEventListener('submit',function(e){
  e.preventDefault();
  var h=parseFloat(document.getElementById('hours').value)||0;
  var r=parseFloat(document.getElementById('rate').value)||0;
  var monthly=h*r*30;
  document.getElementById('result').textContent='Estimated monthly earnings: $'+monthly.toFixed(2);
});

document.getElementById('contactForm').addEventListener('submit',function(e){
  e.preventDefault();
  var name=document.getElementById('name').value.trim();
  var email=document.getElementById('email').value.trim();
  var msg=document.getElementById('msg');
  if(name && email){
    msg.textContent='Thank you, '+name+'! We will contact you at '+email+'.';
    document.getElementById('contactForm').reset();
  }else{
    msg.textContent='Please fill in all fields.';
  }
});