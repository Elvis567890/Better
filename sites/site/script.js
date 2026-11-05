// script.js
const products = [
  {
    id: 1,
    name: "E‑Book: Mastering JavaScript",
    price: 19.99,
    description: "A comprehensive guide to modern JavaScript development.",
    image: "https://via.placeholder.com/300x200?text=JavaScript+E‑Book"
  },
  {
    id: 2,
    name: "UI Kit – 50 Components",
    price: 29.99,
    description: "A ready‑to‑use UI kit with 50 responsive components.",
    image: "https://via.placeholder.com/300x200?text=UI+Kit"
  },
  {
    id: 3,
    name: "Stock Photo Pack (100 images)",
    price: 9.99,
    description: "High‑resolution stock photos for your projects.",
    image: "https://via.placeholder.com/300x200?text=Stock+Photos"
  }
];
let cart = [];

function renderProducts() {
  const container = document.getElementById('product-list');
  container.innerHTML = '';
  products.forEach(p => {
    const card = document.createElement('div');
    card.className = 'product-card';
    card.innerHTML = `
      <img src="${p.image}" alt="${p.name}">
      <div class="info">
        <h3>${p.name}</h3>
        <p>${p.description}</p>
        <div class="price">$${p.price.toFixed(2)}</div>
        <button data-id="${p.id}">View Details</button>
      </div>
    `;
    container.appendChild(card);
  });
}

function openModal(product) {
  const modal = document.getElementById('modal');
  const body = document.getElementById('modal-body');
  body.innerHTML = `
    <h2>${product.name}</h2>
    <img src="${product.image}" alt="${product.name}" style="width:100%;height:auto;">
    <p>${product.description}</p>
    <p class="price">$${product.price.toFixed(2)}</p>
  `;
  document.getElementById('add-to-cart').dataset.id = product.id;
  modal.classList.remove('hidden');
}

function closeModal() {
  document.getElementById('modal').classList.add('hidden');
}

function addToCart(id) {
  const prod = products.find(p => p.id === id);
  if (prod) {
    cart.push(prod);
    document.getElementById('cart-count').textContent = cart.length;
  }
  closeModal();
}

document.addEventListener('DOMContentLoaded', () => {
  renderProducts();

  document.getElementById('product-list').addEventListener('click', e => {
    if (e.target.tagName === 'BUTTON' && e.target.dataset.id) {
      const prod = products.find(p => p.id === parseInt(e.target.dataset.id));
      if (prod) openModal(prod);
    }
  });

  document.querySelector('.close').addEventListener('click', closeModal);
  document.getElementById('add-to-cart').addEventListener('click', e => {
    addToCart(parseInt(e.target.dataset.id));
  });
  window.addEventListener('click', e => {
    if (e.target === document.getElementById('modal')) closeModal();
  });
});