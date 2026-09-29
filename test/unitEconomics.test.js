'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { unitEconomics } = require('../src/unitEconomics');

// Worked examples from NOVAHAUS Blueprint section L.
test('desk mat matches blueprint worked example', () => {
  const r = unitEconomics({ price: 3200, landedCost: 600, shipping: 400, packaging: 100 });
  assert.equal(r.netRevenue, 2667);
  assert.equal(r.paymentFee, 68);
  assert.equal(r.returnsAllowance, 55);
  assert.equal(r.contributionPreAds, 1444);
  assert.equal(r.breakEvenRoas.toFixed(2), '2.22');
  assert.equal(unitEconomics({ price: 3200, landedCost: 600, shipping: 400, packaging: 100, cac: 2000 }).contributionPostAds, -556);
});

test('Desk Reset bundle matches blueprint worked example', () => {
  const r = unitEconomics({ price: 7500, landedCost: 1700, shipping: 650, packaging: 200 });
  assert.equal(r.netRevenue, 6250);
  assert.equal(r.returnsAllowance, 95);
  assert.ok(Math.abs(r.contributionPreAds - 3472) <= 1);
  assert.equal(r.breakEvenRoas.toFixed(2), '2.16');
});

test('rejects invalid inputs and handles loss-making products', () => {
  assert.throws(() => unitEconomics({ price: -1, landedCost: 0, shipping: 0, packaging: 0 }), TypeError);
  assert.throws(() => unitEconomics({ price: 100, landedCost: NaN, shipping: 0, packaging: 0 }), TypeError);
  assert.equal(unitEconomics({ price: 100, landedCost: 500, shipping: 0, packaging: 0 }).breakEvenRoas, Infinity);
});
