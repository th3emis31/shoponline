import type { Metadata } from "next";
import { site } from "@/lib/site";

export const metadata: Metadata = { title: "Contact" };

export default function Contact() {
  return (
    <div className="prose">
      <h1>Contact us</h1>
      <p>
        Email <a href={`mailto:${site.email}`}>{site.email}</a>. We aim to reply within {site.replyTarget}.
      </p>
      <p>Please include your order number if your message is about an order.</p>
      <h2>Business details</h2>
      <p>
        <span className="todo">{site.legalName}</span><br />
        <span className="todo">{site.address}</span>
      </p>
    </div>
  );
}
