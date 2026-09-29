import type { Metadata } from "next";
import Link from "next/link";
import { formatGBP } from "@/lib/money";
import { site } from "@/lib/site";

export const metadata: Metadata = { title: "FAQ" };

const faqs: { q: string; a: React.ReactNode }[] = [
  {
    q: "Why not just buy a cheaper one on a marketplace?",
    a: "We name every material exactly, publish measured dimensions, and dispatch from the UK with simple returns, so you know what you're getting before it arrives.",
  },
  {
    q: "Will it fit my desk?",
    a: "Each product page lists measured dimensions (and, for the cable tray, the desk thicknesses the clamp fits). If you're unsure, email us your desk measurements before ordering.",
  },
  {
    q: "Can I return it?",
    a: <>Yes. You can cancel within {site.returnDays} days of delivery. See <Link href="/returns">returns</Link>.</>,
  },
  {
    q: "How much is delivery?",
    a: <>UK delivery is {formatGBP(site.shippingFee)}, free on orders over {formatGBP(site.freeShippingThreshold)}. See <Link href="/shipping">shipping</Link>.</>,
  },
  {
    q: "Is payment secure?",
    a: "Payment happens on Stripe's hosted checkout. Your card details never reach our servers.",
  },
];

export default function Faq() {
  return (
    <div className="prose">
      <h1>Frequently asked questions</h1>
      {faqs.map((f) => (
        <details key={f.q} className="panel" style={{ marginBottom: 12 }}>
          <summary><strong>{f.q}</strong></summary>
          <p>{f.a}</p>
        </details>
      ))}
    </div>
  );
}
