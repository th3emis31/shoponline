import type { Metadata } from "next";
import { site } from "@/lib/site";

export const metadata: Metadata = { title: "Returns" };

export default function Returns() {
  return (
    <div className="prose">
      <h1>Returns</h1>
      <h2>Your right to cancel</h2>
      <p>
        You can cancel your order within {site.returnDays} days of the day you receive it, for any reason.
        After telling us, you have a further 14 days to send the item back. We refund you within 14 days of
        receiving the item back (or proof you sent it).
      </p>
      <h2>How to return</h2>
      <ol>
        <li>Email <a href={`mailto:${site.email}`}>{site.email}</a> with your order number.</li>
        <li>We reply with the returns address and instructions.</li>
        <li>Pack the item securely and send it back.</li>
        <li>We refund to your original payment method.</li>
      </ol>
      <p className="todo">NEEDS PROFESSIONAL REVIEW before launch: who pays return postage, and faulty-item terms.</p>
    </div>
  );
}
