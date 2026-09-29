import type { Metadata } from "next";
import Link from "next/link";
import { guides } from "@/lib/guides";

export const metadata: Metadata = {
  title: "Buying guides",
  description: "Practical guides for a calmer small home office: cables, desk mats and screen height.",
  alternates: { canonical: "/guides" },
};

export default function Guides() {
  return (
    <div className="prose">
      <h1>Buying guides</h1>
      <p className="lead">Short, practical help for small spaces. No fluff, no made-up numbers.</p>
      <ul className="guide-list" data-testid="guide-list">
        {guides.map((g) => (
          <li key={g.slug}>
            <Link href={`/guides/${g.slug}`}><strong>{g.title}</strong></Link>
            <p className="muted">{g.summary}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
