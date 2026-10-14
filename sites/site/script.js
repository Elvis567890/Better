let interval = null;
let remaining = 0;

const display = document.getElementById('display');
const startBtn = document.getElementById('startBtn');
const pauseBtn = document.getElementById('pauseBtn');
const resetBtn = document.getElementById('resetBtn');
const minutesInput = document.getElementById('minutes');

function formatTime(sec) {
  const m = String(Math.floor(sec / 60)).padStart(2, '0');
  const s = String(sec % 60).padStart(2, '0');
  return `${m}:${s}`;
}

function updateDisplay() {
  display.textContent = formatTime(remaining);
}

function tick() {
  if (remaining > 0) {
    remaining--;
    updateDisplay();
  } else {
    clearInterval(interval);
    interval = null;
    startBtn.disabled = false;
    pauseBtn.disabled = true;
    resetBtn.disabled = false;
    alert('Time is up!');
  }
}

startBtn.addEventListener('click', () => {
  const mins = parseInt(minutesInput.value, 10);
  if (isNaN(mins) || mins < 0) {
    alert('Please enter a valid number of minutes.');
    return;
  }
  remaining = mins * 60;
  updateDisplay();
  interval = setInterval(tick, 1000);
  startBtn.disabled = true;
  pauseBtn.disabled = false;
  resetBtn.disabled = false;
});

pauseBtn.addEventListener('click', () => {
  if (interval) {
    clearInterval(interval);
    interval = null;
    pauseBtn.textContent = 'Resume';
  } else {
    interval = setInterval(tick, 1000);
    pauseBtn.textContent = 'Pause';
  }
});

resetBtn.addEventListener('click', () => {
  clearInterval(interval);
  interval = null;
  remaining = 0;
  updateDisplay();
  startBtn.disabled = false;
  pauseBtn.disabled = true;
  pauseBtn.textContent = 'Pause';
  resetBtn.disabled = true;
});