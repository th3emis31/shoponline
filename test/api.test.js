'use strict';

const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { createApp } = require('../src/app');

let server;
let base;

before(async () => {
  server = http.createServer(createApp());
  await new Promise((r) => server.listen(0, r));
  base = `http://127.0.0.1:${server.address().port}`;
});

after(() => server.close());

const req = async (path, method = 'GET', body) => {
  const res = await fetch(base + path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body),
  });
  return { status: res.status, data: await res.json() };
};

test('full shopping flow over HTTP', async () => {
  const products = await req('/api/products');
  assert.equal(products.status, 200);
  assert.ok(products.data.length > 0);
  assert.equal(products.data[0].landedCost, undefined, 'internal costs must not be exposed');

  const cart = await req('/api/carts', 'POST');
  assert.equal(cart.status, 201);

  const added = await req(`/api/carts/${cart.data.id}/items`, 'POST', { productId: 'desk-mat', quantity: 2 });
  assert.equal(added.status, 200);
  assert.equal(added.data.total, 6400);

  const order = await req(`/api/carts/${cart.data.id}/checkout`, 'POST', {
    name: 'Jane', email: 'jane@example.com', address: '1 Main St',
  });
  assert.equal(order.status, 201);

  const fetched = await req(`/api/orders/${order.data.id}`);
  assert.equal(fetched.data.total, 6400);
});

test('returns clean errors', async () => {
  assert.equal((await req('/api/products/nope')).status, 404);
  assert.equal((await req('/api/carts/nope')).status, 404);
  assert.equal((await req('/api/unknown')).status, 404);
  const cart = await req('/api/carts', 'POST');
  assert.equal((await req(`/api/carts/${cart.data.id}/items`, 'POST', '{bad json')).status, 400);
});

test('serves the storefront and blocks path traversal', async () => {
  const res = await fetch(`${base}/`);
  assert.equal(res.status, 200);
  assert.match(await res.text(), /NOVAHAUS/);
  assert.notEqual((await fetch(`${base}/..%2Fpackage.json`)).status, 200);
});
