/**
 * Business details shown on the site. UK distance-selling rules require the
 * trading name, geographic address and contact email before an order is
 * placed (Blueprint section O).
 *
 * On a hosted shop, set these as environment variables in the hosting
 * dashboard (no code change needed): SHOP_LEGAL_NAME, SHOP_ADDRESS,
 * SHOP_EMAIL, LAUNCH_READY=true, SITE_URL. Changing them redeploys the shop.
 */
const env = (key: string, fallback: string) => {
  const v = process.env[key];
  return v && v.trim() ? v.trim() : fallback;
};

export const site = {
  name: "NOVAHAUS",
  tagline: "Less clutter, better space.",
  legalName: env("SHOP_LEGAL_NAME", "TODO: registered business name"),
  address: env("SHOP_ADDRESS", "TODO: UK business address"),
  email: env("SHOP_EMAIL", "hello@example.com"),
  replyTarget: "1 business day",
  returnDays: 14,
  shippingFee: 395, // pence — must match backend SHIPPING_FEE
  freeShippingThreshold: 5000, // pence — must match backend FREE_SHIPPING_THRESHOLD
  // Preview mode (banner, noindex, waitlist) until you set LAUNCH_READY=true.
  launchReady: env("LAUNCH_READY", "false").toLowerCase() === "true",
  // Public address of the shop, used for canonical links and the sitemap.
  url: env("SITE_URL", "http://localhost:3000").replace(/\/$/, ""),
};
