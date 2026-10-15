// Contact form handling
document.getElementById('contactForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const name = this.name.value.trim();
    const email = this.email.value.trim();
    const message = this.message.value.trim();
    const msgDiv = document.getElementById('contactMsg');
    if (name && email && message) {
        // Simulate async send
        msgDiv.textContent = 'Sending...';
        setTimeout(() => {
            msgDiv.textContent = 'Thank you, ' + name + '! Your message has been sent.';
            this.reset();
        }, 1000);
    } else {
        msgDiv.textContent = 'Please fill in all fields.';
    }
});

// Mock payment gateway handling
document.getElementById('paymentForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const amount = parseFloat(this.amount.value);
    const msgDiv = document.getElementById('paymentMsg');
    if (isNaN(amount) || amount <= 0) {
        msgDiv.textContent = 'Enter a valid amount.';
        return;
    }
    // Simulate payment processing
    msgDiv.textContent = 'Processing payment of $' + amount.toFixed(2) + '...';
    setTimeout(() => {
        // Random success/failure simulation
        if (Math.random() < 0.9) {
            msgDiv.textContent = 'Payment successful! Thank you for your purchase.';
            this.reset();
        } else {
            msgDiv.textContent = 'Payment failed. Please try again.';
        }
    }, 1500);
});