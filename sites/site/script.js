document.addEventListener('DOMContentLoaded', function () {
  const questions = document.querySelectorAll('.faq-question');
  questions.forEach(function (btn) {
    btn.addEventListener('click', function () {
      const answer = btn.nextElementSibling;
      const isOpen = answer.style.display === 'block';
      // Close all answers first
      document.querySelectorAll('.faq-answer').forEach(function (el) {
        el.style.display = 'none';
      });
      // Toggle current answer
      if (!isOpen) {
        answer.style.display = 'block';
      }
    });
  });
});