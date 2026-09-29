'use strict';

// Unit economics model from NOVAHAUS Blueprint section L.
// All money values are in pence. Revenue is ex-VAT so the model still
// holds once the business is VAT-registered.

const VAT_RATE = 0.2;
const STRIPE_UK_PERCENT = 0.015; // FACT: Stripe UK cards 1.5% + 20p
const STRIPE_UK_FIXED = 20;
const RETURN_LABEL = 400; // ASSUMPTION: £4 return label

function paymentFee(priceIncVat) {
  return priceIncVat * STRIPE_UK_PERCENT + STRIPE_UK_FIXED;
}

function unitEconomics({ price, landedCost, shipping, packaging, returnRate = 0.05, cac = 0 }) {
  for (const [name, value] of Object.entries({ price, landedCost, shipping, packaging, returnRate, cac })) {
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
      throw new TypeError(`${name} must be a non-negative number`);
    }
  }
  const netRevenue = price / (1 + VAT_RATE);
  const fee = paymentFee(price);
  const returnsAllowance = returnRate * (shipping + landedCost / 2 + RETURN_LABEL);
  const contributionPreAds = netRevenue - landedCost - shipping - packaging - fee - returnsAllowance;
  return {
    netRevenue: Math.round(netRevenue),
    paymentFee: Math.round(fee),
    returnsAllowance: Math.round(returnsAllowance),
    contributionPreAds: Math.round(contributionPreAds),
    contributionMargin: netRevenue > 0 ? contributionPreAds / netRevenue : 0,
    breakEvenRoas: contributionPreAds > 0 ? price / contributionPreAds : Infinity,
    contributionPostAds: Math.round(contributionPreAds - cac),
  };
}

module.exports = { unitEconomics, paymentFee, VAT_RATE };
