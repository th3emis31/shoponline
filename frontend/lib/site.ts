/**
 * Business details shown on the site. UK distance-selling rules require the
 * trading name, geographic address and contact email before an order is
 * placed (Blueprint section O). Replace every TODO before launch.
 */
export const site = {
  name: "NOVAHAUS",
  tagline: "Less clutter, better space.",
  legalName: "TODO: registered business name",
  address: "TODO: UK business address",
  email: "hello@example.com", // TODO: real support inbox
  replyTarget: "1 business day",
  returnDays: 14,
  shippingFee: 395, // pence — must match backend SHIPPING_FEE
  freeShippingThreshold: 5000, // pence — must match backend FREE_SHIPPING_THRESHOLD
  launchReady: false, // flip only when every section O gate is green
};
