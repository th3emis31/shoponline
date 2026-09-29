import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AddToCart from "@/components/AddToCart";
import Illustration from "@/components/Illustration";
import TrackView from "@/components/TrackView";
import WaitlistForm from "@/components/WaitlistForm";
import { getProduct, getProducts } from "@/lib/api";
import { BUNDLE_ID, BUNDLE_PARTS, entry } from "@/lib/catalog";
import { jsonLdScript, productJsonLd } from "@/lib/jsonld";
import { formatGBP } from "@/lib/money";
import { site } from "@/lib/site";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const product = await getProduct((await params).id);
  if (!product) return { title: "Product not found" };
  const description = `${product.name}. ${formatGBP(product.price)} inc. VAT, UK delivery, ${site.returnDays}-day returns.`;
  return {
    title: product.name,
    description,
    alternates: { canonical: `/products/${product.id}` },
    openGraph: { title: product.name, description, type: "website", url: `/products/${product.id}` },
  };
}

export default async function ProductPage({ params }: Props) {
  const product = await getProduct((await params).id);
  if (!product) notFound();

  const copy = entry(product.id);
  const all = await getProducts().catch(() => []);
  const isPart = (id: string) => (BUNDLE_PARTS as readonly string[]).includes(id);
  // A set shows its pieces; a piece of the set shows the set and the other pieces.
  const related = product.is_bundle
    ? all.filter((p) => isPart(p.id))
    : isPart(product.id)
      ? all.filter((p) => p.id === BUNDLE_ID || (isPart(p.id) && p.id !== product.id))
      : all.filter((p) => p.id === BUNDLE_ID);
  const bundle = all.find((p) => p.id === BUNDLE_ID);
  const setSaving = bundle ? all.filter((p) => isPart(p.id)).reduce((n, p) => n + p.price, 0) - bundle.price : 0;

  return (
    <div className="product">
      <TrackView productId={product.id} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(productJsonLd(product)) }} />
      <div className="product-media"><Illustration id={product.id} /></div>
      <div>
        {product.is_bundle && <span className="badge">Best value set</span>}
        <h1>{product.name}</h1>
        <p className="price" style={{ fontSize: "1.4rem" }}>
          {formatGBP(product.price)} <span className="muted">inc. VAT</span>
        </p>
        {copy && <p className="lead">{copy.tagline}</p>}
        <div className="sticky-cta">
          <AddToCart productId={product.id} inStock={product.in_stock} />
        </div>
        <ul className="ticks">
          <li>UK delivery {formatGBP(site.shippingFee)}, free over {formatGBP(site.freeShippingThreshold)}</li>
          <li>{site.returnDays}-day returns</li>
          <li>Secure payment by Stripe</li>
        </ul>

        {copy && (
          <>
            <h2>Why you&apos;ll like it</h2>
            <p className="muted">{copy.problem}</p>
            <ul className="benefits">{copy.benefits.map((b) => <li key={b}>{b}</li>)}</ul>
            <h2>What&apos;s included</h2>
            <ul>{copy.included.map((b) => <li key={b}>{b}</li>)}</ul>
          </>
        )}

        <h2>Specifications</h2>
        {/* Blueprint rule: specs come from the physical sample, never copied or guessed. */}
        {!copy?.verified && (
          <p className="muted">Exact dimensions, materials and load ratings are published once measured on the approved sample.</p>
        )}

        {related.length > 0 && (
          <>
            <h2>{product.is_bundle ? "In this set" : "Complete the set"}</h2>
            <div className="mini-grid">
              {related.map((r) => (
                <Link key={r.id} href={`/products/${r.id}`} className="mini">
                  <Illustration id={r.id} caption={false} />
                  <span>{r.name}</span>
                  <strong>{formatGBP(r.price)}</strong>
                </Link>
              ))}
            </div>
            {!product.is_bundle && setSaving > 0 && (
              <p className="muted small">The Desk Reset set saves {formatGBP(setSaving)} compared with buying the pieces separately.</p>
            )}
          </>
        )}

        {!site.launchReady && (
          <>
            <h2>Get launch news</h2>
            <WaitlistForm productId={product.id} />
          </>
        )}

        <h2>Delivery &amp; returns</h2>
        <ul>
          <li>UK delivery {formatGBP(site.shippingFee)}, free over {formatGBP(site.freeShippingThreshold)}. <Link href="/shipping">Details</Link></li>
          <li>{site.returnDays}-day cancellation right from delivery. <Link href="/returns">How returns work</Link></li>
        </ul>
      </div>
    </div>
  );
}
