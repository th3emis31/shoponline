import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AddToCart from "@/components/AddToCart";
import { getProduct } from "@/lib/api";
import { formatGBP } from "@/lib/money";
import { site } from "@/lib/site";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const product = await getProduct((await params).id);
  return { title: product?.name ?? "Product not found" };
}

export default async function ProductPage({ params }: Props) {
  const product = await getProduct((await params).id);
  if (!product) notFound();

  return (
    <div className="product">
      <div className="ph" aria-hidden="true">Photos will be taken from the sample in hand</div>
      <div>
        {product.is_bundle && <span className="badge">Bundle</span>}
        <h1>{product.name}</h1>
        <p className="price" style={{ fontSize: "1.4rem" }}>
          {formatGBP(product.price)} <span className="muted">inc. VAT</span>
        </p>
        <div className="sticky-cta">
          <AddToCart productId={product.id} inStock={product.in_stock} />
        </div>

        <h2>Specifications</h2>
        {/* Blueprint rule: specs come from the physical sample, never copied or guessed. */}
        <p className="muted">Exact dimensions, materials and what&apos;s in the box will be listed once measured from the approved sample.</p>

        <h2>Delivery &amp; returns</h2>
        <ul>
          <li>UK delivery {formatGBP(site.shippingFee)}, free over {formatGBP(site.freeShippingThreshold)}. <Link href="/shipping">Details</Link></li>
          <li>{site.returnDays}-day cancellation right from delivery. <Link href="/returns">How returns work</Link></li>
        </ul>
      </div>
    </div>
  );
}
