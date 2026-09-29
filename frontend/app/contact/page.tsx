import type { Metadata } from "next";
import ContactForm from "@/components/ContactForm";
import { site } from "@/lib/site";

export const metadata: Metadata = { title: "Contact" };

export default function Contact() {
  return (
    <div className="prose">
      <h1>Contact us</h1>
      <p>
        Send us a message below, or email <a href={`mailto:${site.email}`}>{site.email}</a>.
        A person replies within {site.replyTarget}.
      </p>
      <ContactForm />
      <h2>Business details</h2>
      <p>
        <span className="todo">{site.legalName}</span><br />
        <span className="todo">{site.address}</span>
      </p>
    </div>
  );
}
