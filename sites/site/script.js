document.addEventListener('DOMContentLoaded', function () {
    const navToggle = document.getElementById('nav-toggle');
    const navList = document.querySelector('.nav-list');

    navToggle.addEventListener('click', function () {
        navList.classList.toggle('show');
        // Animate hamburger
        this.classList.toggle('active');
    });

    // Close menu when a link is clicked (mobile)
    document.querySelectorAll('.nav-list a').forEach(link => {
        link.addEventListener('click', () => {
            if (navList.classList.contains('show')) {
                navList.classList.remove('show');
                navToggle.classList.remove('active');
            }
        });
    });
});