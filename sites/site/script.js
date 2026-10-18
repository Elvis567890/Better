document.addEventListener('DOMContentLoaded', function(){
    const btn = document.querySelector('.contact-btn');
    if(btn){
        btn.addEventListener('click', function(e){
            e.preventDefault();
            const url = btn.getAttribute('href');
            window.open(url, '_blank');
        });
    }
});