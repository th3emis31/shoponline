'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { listProducts, findProduct, toPublic } = require('./products');
const { Shop, ShopError } = require('./shop');

const PUBLIC_DIR = path.join(__dirname, '..', 'public');
const MAX_BODY_BYTES = 1e5;
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css' };

function sendJson(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk) => {
      body += chunk;
      if (body.length > MAX_BODY_BYTES) {
        reject(new ShopError('Request body too large', 413));
        req.destroy();
      }
    });
    req.on('end', () => {
      if (!body) return resolve({});
      try {
        resolve(JSON.parse(body));
      } catch {
        reject(new ShopError('Invalid JSON body'));
      }
    });
    req.on('error', reject);
  });
}

function serveStatic(res, urlPath) {
  const file = urlPath === '/' ? 'index.html' : urlPath.slice(1);
  const fullPath = path.normalize(path.join(PUBLIC_DIR, file));
  if (!fullPath.startsWith(PUBLIC_DIR)) return sendJson(res, 403, { error: 'Forbidden' });
  fs.readFile(fullPath, (err, data) => {
    if (err) return sendJson(res, 404, { error: 'Not found' });
    res.writeHead(200, { 'Content-Type': MIME[path.extname(fullPath)] || 'application/octet-stream' });
    res.end(data);
  });
}

function createApp(shop = new Shop()) {
  return async function handler(req, res) {
    const { pathname } = new URL(req.url, 'http://localhost');
    const parts = pathname.split('/').filter(Boolean);
    try {
      if (parts[0] !== 'api') return serveStatic(res, pathname);

      // GET /api/products, GET /api/products/:id
      if (parts[1] === 'products' && req.method === 'GET') {
        if (parts.length === 2) return sendJson(res, 200, listProducts());
        const product = findProduct(parts[2]);
        return product ? sendJson(res, 200, toPublic(product)) : sendJson(res, 404, { error: 'Product not found' });
      }

      if (parts[1] === 'carts') {
        // POST /api/carts
        if (parts.length === 2 && req.method === 'POST') {
          return sendJson(res, 201, shop.getCart(shop.createCart()));
        }
        const cartId = parts[2];
        // GET /api/carts/:id
        if (parts.length === 3 && req.method === 'GET') return sendJson(res, 200, shop.getCart(cartId));
        // POST /api/carts/:id/items  { productId, quantity }
        if (parts[3] === 'items' && parts.length === 4 && req.method === 'POST') {
          const { productId, quantity = 1 } = await readJson(req);
          return sendJson(res, 200, shop.addItem(cartId, productId, quantity));
        }
        // DELETE /api/carts/:id/items/:productId
        if (parts[3] === 'items' && parts.length === 5 && req.method === 'DELETE') {
          return sendJson(res, 200, shop.removeItem(cartId, parts[4]));
        }
        // POST /api/carts/:id/checkout  { name, email, address }
        if (parts[3] === 'checkout' && req.method === 'POST') {
          return sendJson(res, 201, shop.checkout(cartId, await readJson(req)));
        }
      }

      // GET /api/orders/:id
      if (parts[1] === 'orders' && parts.length === 3 && req.method === 'GET') {
        return sendJson(res, 200, shop.getOrder(parts[2]));
      }

      return sendJson(res, 404, { error: 'Not found' });
    } catch (err) {
      if (err instanceof ShopError) return sendJson(res, err.status, { error: err.message });
      console.error(err);
      return sendJson(res, 500, { error: 'Internal server error' });
    }
  };
}

module.exports = { createApp };
