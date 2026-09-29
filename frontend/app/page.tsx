import Link from "next/link";
import Illustration from "@/components/Illustration";
import ProductCard from "@/components/ProductCard";
import WaitlistForm from "@/components/WaitlistForm";
import { getProducts } from "@/lib/api";
import { BUNDLE_ID, BUNDLE_PARTS } from "@/lib/catalog";
import { formatGBP } from "@/lib/money";
import { site } from "@/lib/site";

export const dynamic = "force-dynamic";

const PROBLEMS = [
  { title: "Cables everywhere", text: "Chargers hanging under the desk and falling behind it. The tray and clips put every cable in its place, without drilling." },
  { title: "A desk that looks unfinished", text: "A felt and vegan-leather mat gives the whole setup a calm base, and protects the desk underneath." },
  { title: "Screen too low", text: "The oak riser brings your screen up and hides the small stuff in a drawer." },
];

const WHY = [
  { title: "Honest materials", text: "Felt, walnut, oak and steel, named exactly. No mystery plastics." },
  { title: "Made for small UK homes", text: "Renter-friendly, no-drill designs sized for real flats and home offices." },
  { title: "Easy to return", text: `${site.returnDays}-day cancellation right from delivery, in plain English.` },
];

export default async function Home() {
  const products = await getProducts();
  const bundle = products.find((p) => p.id === BUNDLE_ID);
  const singles = products.filter((p) => !p.is_bundle);
  const partsPrice = products
    .filter((p) => (BUNDLE_PARTS as readonly string[]).includes(p.id))
    .reduce((sum, p) => sum + p.price, 0);
  const saving = bundle ? partsPrice - bundle.price : 0;

  return (
    <>
      <section className="hero">
        <div className="hero-text">
          <p className="eyebrow">The Desk Reset collection</p>
          <h1>Calm, organised desks for small UK homes.</h1>
          <p className="lead">Well-made organisation pieces in honest materials, with exact dimensions and easy returns.</p>
          <div className="cta-row">
            <Link className="btn" href={bundle ? `/products/${bundle.id}` : "/shop"}>Shop the Desk Reset set</Link>
            <Link className="btn secondary" href="/shop">See every piece</Link>
          </div>
          {bundle && saving > 0 && (
            <p className="muted small">The set: {formatGBP(bundle.price)} instead of {formatGBP(partsPrice)} bought separately.</p>
          )}
        </div>
        <div className="hero-art"><Illustration id="hero" /></div>
      </section>

      <section className="trust" aria-label="Why shop with us">
        <div><strong>Dispatched from the UK</strong><span>Tracked delivery</span></div>
        <div><strong>{site.returnDays}-day returns</strong><span>Plain-English policy</span></div>
        <div><strong>Secure payment</strong><span>Card details handled by Stripe</span></div>
        <div><strong>Free delivery</strong><span>on orders over {formatGBP(site.freeShippingThreshold)}</span></div>
      </section>

      <h2>Small space, messy desk?</h2>
      <div className="three">
        {PROBLEMS.map((p) => (
          <div key={p.title} className="panel"><h3>{p.title}</h3><p>{p.text}</p></div>
        ))}
      </div>

      <h2>The collection</h2>
      <div className="grid">
        {singles.map((p) => <ProductCard key={p.id} product={p} />)}
      </div>

      {bundle && (
        <section className="feature" aria-labelledby="set-heading">
          <div>
            <p className="eyebrow">Best value</p>
            <h2 id="set-heading">The Desk Reset set</h2>
            <p>Desk mat, under-desk cable tray and walnut cable clips, designed to work together and sent in one parcel.</p>
            {saving > 0 && (
              <p><strong>{formatGBP(bundle.price)}</strong> <span className="muted">instead of {formatGBP(partsPrice)}. You save {formatGBP(saving)}.</span></p>
            )}
            <Link className="btn" href={`/products/${bundle.id}`}>View the set</Link>
          </div>
          <ProductCard product={bundle} savings={saving} />
        </section>
      )}

      <h2>Why NOVAHAUS</h2>
      <div className="three">
        {WHY.map((w) => (
          <div key={w.title} className="panel"><h3>{w.title}</h3><p>{w.text}</p></div>
        ))}
      </div>

      {!site.launchReady && (
        <section className="feature soft" id="launch" aria-labelledby="launch-heading">
          <div>
            <h2 id="launch-heading">Be first when we launch</h2>
            <p className="muted">We&apos;re testing the first products now. Leave your email and we&apos;ll send you one message when the shop opens.</p>
          </div>
          <WaitlistForm />
        </section>
      )}

      <h2>Questions?</h2>
      <p>Delivery, returns and sizing are covered in our <Link href="/faq">FAQ</Link>.</p>
    </>
  );
}
