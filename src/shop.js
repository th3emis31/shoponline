'use strict';

const crypto = require('node:crypto');
const { findProduct } = require('./products');

const MAX_QTY_PER_ITEM = 99;

class ShopError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.status = status;
  }
}

class Shop {
  constructor() {
    this.carts = new Map(); // cartId -> Map(productId -> qty)
    this.orders = new Map(); // orderId -> order
  }

  createCart() {
    const id = crypto.randomUUID();
    this.carts.set(id, new Map());
    return id;
  }

  getCartItems(cartId) {
    const cart = this.carts.get(cartId);
    if (!cart) throw new ShopError('Cart not found', 404);
    return cart;
  }

  addItem(cartId, productId, quantity = 1) {
    const cart = this.getCartItems(cartId);
    const product = findProduct(productId);
    if (!product) throw new ShopError('Product not found', 404);
    if (!Number.isInteger(quantity) || quantity < 1) {
      throw new ShopError('Quantity must be a positive integer');
    }
    const newQty = (cart.get(productId) || 0) + quantity;
    if (newQty > MAX_QTY_PER_ITEM) throw new ShopError(`Maximum ${MAX_QTY_PER_ITEM} per item`);
    if (newQty > product.stock) throw new ShopError('Not enough stock', 409);
    cart.set(productId, newQty);
    return this.getCart(cartId);
  }

  removeItem(cartId, productId) {
    const cart = this.getCartItems(cartId);
    cart.delete(productId);
    return this.getCart(cartId);
  }

  getCart(cartId) {
    const cart = this.getCartItems(cartId);
    const items = [];
    let total = 0;
    for (const [productId, quantity] of cart) {
      const product = findProduct(productId);
      if (!product) continue;
      const lineTotal = product.price * quantity;
      total += lineTotal;
      items.push({ productId, name: product.name, price: product.price, quantity, lineTotal });
    }
    return { id: cartId, items, total };
  }

  checkout(cartId, customer) {
    const cart = this.getCart(cartId);
    if (cart.items.length === 0) throw new ShopError('Cart is empty');
    validateCustomer(customer);

    // Verify all stock first so a failed checkout never partially deducts stock.
    for (const item of cart.items) {
      if (item.quantity > findProduct(item.productId).stock) {
        throw new ShopError(`Not enough stock for ${item.name}`, 409);
      }
    }
    for (const item of cart.items) {
      findProduct(item.productId).stock -= item.quantity;
    }

    const order = {
      id: crypto.randomUUID(),
      items: cart.items,
      total: cart.total,
      customer: { name: customer.name.trim(), email: customer.email.trim(), address: customer.address.trim() },
      status: 'placed',
      createdAt: new Date().toISOString(),
    };
    this.orders.set(order.id, order);
    this.carts.delete(cartId);
    return order;
  }

  getOrder(orderId) {
    const order = this.orders.get(orderId);
    if (!order) throw new ShopError('Order not found', 404);
    return order;
  }
}

function validateCustomer(customer) {
  if (!customer || typeof customer !== 'object') throw new ShopError('Customer details required');
  for (const field of ['name', 'email', 'address']) {
    if (typeof customer[field] !== 'string' || customer[field].trim() === '') {
      throw new ShopError(`Customer ${field} is required`);
    }
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(customer.email.trim())) {
    throw new ShopError('Customer email is invalid');
  }
}

module.exports = { Shop, ShopError };
