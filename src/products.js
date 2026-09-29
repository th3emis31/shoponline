'use strict';

// NOVAHAUS "Desk Reset" validation shortlist (Blueprint sections E/F).
// Prices are inc. VAT, in pence. All prices and landed costs are ESTIMATES
// until replaced by real supplier quotes. Stock values are placeholders:
// no stock is held until the launch gate is approved.
const products = [
  { id: 'desk-mat', name: 'Felt + Vegan-Leather Desk Mat, 90×40 cm', price: 3200, landedCost: 600, shipping: 400, packaging: 100, stock: 50 },
  { id: 'cable-tray', name: 'Clamp-On Under-Desk Cable Tray (steel, no drilling)', price: 3400, landedCost: 800, shipping: 450, packaging: 100, stock: 50 },
  { id: 'cable-clips', name: 'Walnut + Silicone Cable Clip Set', price: 1800, landedCost: 300, shipping: 250, packaging: 50, stock: 50 },
  { id: 'monitor-riser', name: 'Oak Monitor Riser with Drawer', price: 5900, landedCost: 1600, shipping: 650, packaging: 150, stock: 20 },
  { id: 'desk-reset', name: 'Desk Reset Bundle (mat + cable tray + clips)', price: 7500, landedCost: 1700, shipping: 650, packaging: 200, stock: 20, bundle: true },
];

// Public view: never expose internal cost fields to shoppers.
function toPublic({ id, name, price, stock, bundle = false }) {
  return { id, name, price, inStock: stock > 0, bundle };
}

function listProducts() {
  return products.map(toPublic);
}

function findProduct(id) {
  return products.find((p) => p.id === id) || null;
}

module.exports = { listProducts, findProduct, toPublic, products };
