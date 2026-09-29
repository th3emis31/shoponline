import type { Metadata } from "next";
import { formatGBP } from "@/lib/money";
import { site } from "@/lib/site";

export const metadata: Metadata = { title: "Shipping" };

export default function Shipping() {
  return (
    <div className="prose">
      <h1>Shipping</h1>
      <ul>
        <li>UK delivery: {formatGBP(site.shippingFee)} per order.</li>
        <li>Free UK delivery on orders over {formatGBP(site.freeShippingThreshold)}.</li>
        <li>Delivery costs are always shown in your cart before payment.</li>
      </ul>
      <p className="todo">TODO before launch: carrier name, dispatch cut-off time and delivery times, once the carrier account is set up.</p>
    </div>
  );
}
