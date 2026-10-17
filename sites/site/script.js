document.getElementById('bookBtn').addEventListener('click', function () {
  document.getElementById('modal').classList.remove('hidden');
});

document.querySelector('.close').addEventListener('click', function () {
  document.getElementById('modal').classList.add('hidden');
});

window.addEventListener('click', function (e) {
  if (e.target === document.getElementById('modal')) {
    document.getElementById('modal').classList.add('hidden');
  }
});

document.getElementById('bookingForm').addEventListener('submit', function (e) {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(this));
  const time = data.time ? new Date(data.time).toLocaleString() : 'your chosen time';
  alert(`Thank you, ${data.name}! Your free ride is booked for ${time}.`);
  this.reset();
  document.getElementById('modal').classList.add('hidden');
});