import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getProducts } from "@/lib/api";
import { jsonLdScript } from "@/lib/jsonld";
import { guide, guides } from "@/lib/guides";
import { formatGBP } from "@/lib/money";
import { site } from "@/lib/site";

type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return guides.map((g) => ({ slug: g.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const g = guide((await params).slug);
  if (!g) return { title: "Guide not found" };
  return { title: g.title, description: g.summary, alternates: { canonical: `/guides/${g.slug}` } };
}

export default async function GuidePage({ params }: Props) {
  const g = guide((await params).slug);
  if (!g) notFound();
  const products = (await getProducts().catch(() => [])).filter((p) => g.products.includes(p.id));
  const ld = { "@context": "https://schema.org", "@type": "Article", headline: g.title, description: g.summary,
    publisher: { "@type": "Organization", name: site.name }, url: `${site.url}/guides/${g.slug}` };
  return (
    <article className="prose">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(ld) }} />
      <p className="small"><Link href="/guides">Buying guides</Link></p>
      <h1>{g.title}</h1>
      <p className="lead">{g.summary}</p>
      {g.body.map((b, i) => (
        <div key={i}>
          {b.h && <h2>{b.h}</h2>}
          {b.p && <p>{b.p}</p>}
          {b.list && <ul>{b.list.map((x) => <li key={x}>{x}</li>)}</ul>}
        </div>
      ))}
      {products.length > 0 && (
        <>
          <h2>From our shop</h2>
          <ul>
            {products.map((p) => <li key={p.id}><Link href={`/products/${p.id}`}>{p.name}</Link>: {formatGBP(p.price)}</li>)}
          </ul>
        </>
      )}
    </article>
  );
}
