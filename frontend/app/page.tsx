import Link from "next/link";
import ProductCard from "@/components/ProductCard";
import { getProducts } from "@/lib/api";
import { formatGBP } from "@/lib/money";
import { site } from "@/lib/site";

export const dynamic = "force-dynamic";

export default async function Home() {
  const products = await getProducts();
  const bundle = products.find((p) => p.is_bundle);
  const singles = products.filter((p) => !p.is_bundle);
  const BUNDLE_PARTS = ["desk-mat", "cable-tray", "cable-clips"];
  const partsPrice = products
    .filter((p) => BUNDLE_PARTS.includes(p.id))
    .reduce((sum, p) => sum + p.price, 0);

  return (
    <>
      <section className="hero">
        <h1>Calm, organised desks for small UK homes.</h1>
        <p>Well-made organisation pieces in honest materials, with exact dimensions and easy returns.</p>
        <Link className="btn" href={bundle ? `/products/${bundle.id}` : "/shop"}>Shop the Desk Reset set</Link>
      </section>

      <section className="trust" aria-label="Why shop with us">
        <div><strong>Dispatched from the UK</strong><br />Tracked delivery</div>
        <div><strong>{site.returnDays}-day returns</strong><br />Plain-English returns policy</div>
        <div><strong>Secure payment</strong><br />Card details handled by Stripe</div>
      </section>

      <h2>Small space, messy desk?</h2>
      <p className="prose">
        Cables hanging under the desk, a scratched worktop and a screen that sits too low. The Desk Reset
        pieces fix each of those, and they&apos;re designed to be used together.
      </p>

      <h2>The collection</h2>
      <div className="grid">
        {singles.map((p) => <ProductCard key={p.id} product={p} />)}
      </div>

      {bundle && (
        <>
          <h2>The Desk Reset set</h2>
          <div className="grid">
            <ProductCard product={bundle} />
            <div className="panel">
              <p>Desk mat, under-desk cable tray and cable clips in one parcel.</p>
              {partsPrice > bundle.price && (
                <p className="muted">
                  Bought separately: {formatGBP(partsPrice)}. As a set: {formatGBP(bundle.price)}.
                </p>
              )}
            </div>
          </div>
        </>
      )}

      <h2>Questions?</h2>
      <p>Delivery, returns and sizing are covered in our <Link href="/faq">FAQ</Link>.</p>
    </>
  );
}
