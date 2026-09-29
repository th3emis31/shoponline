import type { Metadata } from "next";

export const metadata: Metadata = { title: "Terms of sale" };

export default function TermsPage() {
  return (
    <div className="prose">
      <h1>Terms of sale</h1>
      <p className="todo">
        Draft placeholder. This page must be written and reviewed by a qualified professional before launch
        (NOVAHAUS Blueprint section O: legal pages gate).
      </p>
    </div>
  );
}
