import Link from "next/link";
import { formatGBP } from "@/lib/money";
import type { Product } from "@/lib/types";
import AddToCart from "./AddToCart";

export default function ProductCard({ product }: { product: Product }) {
  return (
    <article className="card" data-testid="product-card">
      {/* Placeholder until real photos of the sample in hand exist (no stock imagery). */}
      <div className="ph" aria-hidden="true">Photo coming from sample</div>
      {product.is_bundle && <span className="badge">Bundle</span>}
      <Link className="title" href={`/products/${product.id}`}>{product.name}</Link>
      <span className="price">{formatGBP(product.price)} <span className="muted">inc. VAT</span></span>
      <AddToCart productId={product.id} inStock={product.in_stock} />
    </article>
  );
}
