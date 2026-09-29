'use strict';

const { test, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const { Shop, ShopError } = require('../src/shop');
const { products } = require('../src/products');

const initialStock = products.map((p) => p.stock);
const customer = { name: 'Jane Doe', email: 'jane@example.com', address: '1 Main St' };
let shop;

beforeEach(() => {
  products.forEach((p, i) => { p.stock = initialStock[i]; });
  shop = new Shop();
});

test('adds items and computes totals in cents', () => {
  const id = shop.createCart();
  shop.addItem(id, 'desk-mat', 2);
  const cart = shop.addItem(id, 'monitor-riser', 1);
  assert.equal(cart.total, 3200 * 2 + 5900);
  assert.equal(cart.items.length, 2);
});

test('rejects unknown product, bad quantity and over-stock', () => {
  const id = shop.createCart();
  assert.throws(() => shop.addItem(id, 'nope'), { status: 404 });
  assert.throws(() => shop.addItem(id, 'desk-mat', 0), ShopError);
  assert.throws(() => shop.addItem(id, 'desk-mat', 1.5), ShopError);
  assert.throws(() => shop.addItem(id, 'monitor-riser', 21), { status: 409 });
});

test('removes items', () => {
  const id = shop.createCart();
  shop.addItem(id, 'desk-mat', 1);
  assert.equal(shop.removeItem(id, 'desk-mat').items.length, 0);
});

test('checkout creates order, deducts stock and clears cart', () => {
  const id = shop.createCart();
  shop.addItem(id, 'cable-clips', 3);
  const order = shop.checkout(id, customer);
  assert.equal(order.total, 1800 * 3);
  assert.equal(products.find((p) => p.id === 'cable-clips').stock, initialStock[products.findIndex((p) => p.id === 'cable-clips')] - 3);
  assert.deepEqual(shop.getOrder(order.id), order);
  assert.throws(() => shop.getCart(id), { status: 404 });
});

test('checkout validates cart and customer', () => {
  const id = shop.createCart();
  assert.throws(() => shop.checkout(id, customer), /Cart is empty/);
  shop.addItem(id, 'desk-mat', 1);
  assert.throws(() => shop.checkout(id, { ...customer, email: 'bad' }), /email is invalid/);
  assert.throws(() => shop.checkout(id, { ...customer, name: ' ' }), /name is required/);
});

test('failed checkout does not partially deduct stock', () => {
  const a = shop.createCart();
  const b = shop.createCart();
  shop.addItem(a, 'desk-mat', 1);
  shop.addItem(a, 'monitor-riser', 20);
  shop.addItem(b, 'monitor-riser', 1);
  shop.checkout(b, customer); // monitor-riser stock now 19
  assert.throws(() => shop.checkout(a, customer), { status: 409 });
  assert.equal(products.find((p) => p.id === 'desk-mat').stock, initialStock[0]);
});
