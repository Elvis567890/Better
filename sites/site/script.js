// Simple interactivity for demo purposes

document.addEventListener('DOMContentLoaded', function () {
  const downloadBtn = document.getElementById('downloadBtn');
  const selectButtons = document.querySelectorAll('.selectBtn');

  if (downloadBtn) {
    downloadBtn.addEventListener('click', function () {
      alert('Thank you! The download will be available soon.');
    });
  }

  selectButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      alert('You selected the ' + this.parentElement.querySelector('h3').textContent + ' plan.');
    });
  });
});