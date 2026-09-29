const money = (pence) => `£${(pence / 100).toFixed(2)}`;
const $ = (sel) => document.querySelector(sel);
let cartId = localStorage.getItem('cartId');

async function api(url, options = {}) {
  const res = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function showMessage(text, isError = false) {
  const el = $('#message');
  el.textContent = text;
  el.className = isError ? 'error' : '';
}

async function ensureCart() {
  if (cartId) {
    try { return await api(`/api/carts/${cartId}`); } catch { /* expired, create a new one */ }
  }
  const cart = await api('/api/carts', { method: 'POST' });
  cartId = cart.id;
  localStorage.setItem('cartId', cartId);
  return cart;
}

function renderCart(cart) {
  const list = $('#cart-items');
  list.innerHTML = '';
  for (const item of cart.items) {
    const li = document.createElement('li');
    li.textContent = `${item.name} x${item.quantity} — ${money(item.lineTotal)} `;
    const btn = document.createElement('button');
    btn.textContent = '×';
    btn.className = 'remove';
    btn.onclick = async () => renderCart(await api(`/api/carts/${cartId}/items/${item.productId}`, { method: 'DELETE' }));
    li.appendChild(btn);
    list.appendChild(li);
  }
  $('#cart-total').textContent = money(cart.total);
  $('#cart-count').textContent = `Cart: ${cart.items.reduce((n, i) => n + i.quantity, 0)}`;
}

async function renderProducts() {
  const products = await api('/api/products');
  const container = $('#products');
  for (const p of products) {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `<h3></h3><p></p><button>Add to cart</button>`;
    card.querySelector('h3').textContent = p.name;
    card.querySelector('p').textContent = `${money(p.price)} inc. VAT${p.inStock ? '' : ' · Out of stock'}`;
    if (!p.inStock) card.querySelector('button').disabled = true;
    card.querySelector('button').onclick = async () => {
      try {
        renderCart(await api(`/api/carts/${cartId}/items`, { method: 'POST', body: JSON.stringify({ productId: p.id, quantity: 1 }) }));
        showMessage(`${p.name} added to cart`);
      } catch (err) { showMessage(err.message, true); }
    };
    container.appendChild(card);
  }
}

$('#checkout-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
  try {
    const order = await api(`/api/carts/${cartId}/checkout`, { method: 'POST', body: JSON.stringify(body) });
    showMessage(`Order placed! Order ID: ${order.id} — Total ${money(order.total)}`);
    e.target.reset();
    localStorage.removeItem('cartId');
    cartId = null;
    renderCart(await ensureCart());
  } catch (err) { showMessage(err.message, true); }
});

(async () => {
  renderCart(await ensureCart());
  await renderProducts();
})();
