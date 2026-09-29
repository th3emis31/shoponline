import type { Metadata } from "next";

export const metadata: Metadata = { title: "Cookie policy" };

export default function CookiesPage() {
  return (
    <div className="prose">
      <h1>Cookie policy</h1>
      <p className="todo">
        Draft placeholder. This page must be written and reviewed by a qualified professional before launch
        (NOVAHAUS Blueprint section O: legal pages gate).
      </p>
      <h2>What this site stores on your device today</h2>
      <p>No cookies for advertising or tracking, and no third-party trackers. Only:</p>
      <ul>
        <li><strong>Your cart number</strong> (browser storage), so your cart is still there when you come back.</li>
        <li><strong>Your order email</strong> (only for this tab), so your order page can show your order after payment.</li>
        <li>
          <strong>The ad campaign name</strong> (only for this tab) if you arrived through one of our ads, so we can
          tell which ads lead to orders. It holds only the campaign name, never anything about you, and is deleted
          when you close the tab.
        </li>
      </ul>
      <p>Payment happens on Stripe&apos;s own page, which has its own cookie policy.</p>
    </div>
  );
}
