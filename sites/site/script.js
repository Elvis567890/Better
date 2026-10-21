// script.js – handles the "Join Now" SMS action

document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('joinForm');
  const phoneInput = document.getElementById('phone');

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    const phone = phoneInput.value.trim();
    if (!phone) {
      alert('Please enter a valid phone number.');
      return;
    }

    // Build a simple SMS link. The body contains a placeholder join link.
    const message = encodeURIComponent('Join Instant Drive Jobs: https://example.com/join?phone=' + encodeURIComponent(phone));
    const smsLink = `sms:${phone}?body=${message}`;

    // Try to open the SMS app. If the device cannot handle the scheme, fall back to an alert.
    window.location.href = smsLink;
  });
});