// Simple interaction: add a tiny bounce effect on button click
document.querySelectorAll('.btn').forEach(function(btn) {
  btn.addEventListener('click', function(e) {
    btn.classList.add('active');
    setTimeout(function() { btn.classList.remove('active'); }, 150);
  });
});

/* Add CSS for the active state (injected via JS) */
var style = document.createElement('style');
style.innerHTML = " .btn.active { transform: scale(0.96); } ";
document.head.appendChild(style);
