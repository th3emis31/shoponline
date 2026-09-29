import Link from "next/link";
import { entry } from "@/lib/catalog";
import { formatGBP } from "@/lib/money";
import type { Product } from "@/lib/types";
import AddToCart from "./AddToCart";
import Illustration from "./Illustration";

export default function ProductCard({ product, savings }: { product: Product; savings?: number }) {
  const copy = entry(product.id);
  return (
    <article className="card" data-testid="product-card">
      <Link href={`/products/${product.id}`} className="card-media" tabIndex={-1} aria-hidden="true">
        <Illustration id={product.id} caption={false} />
      </Link>
      <div className="card-body">
        {product.is_bundle && <span className="badge">Best value set</span>}
        <Link className="title" href={`/products/${product.id}`}>{product.name}</Link>
        {copy && <p className="muted small">{copy.tagline}</p>}
        <p className="price">
          {formatGBP(product.price)} <span className="muted small">inc. VAT</span>
          {savings && savings > 0 ? <span className="save">Save {formatGBP(savings)}</span> : null}
        </p>
        <AddToCart productId={product.id} inStock={product.in_stock} />
      </div>
    </article>
  );
}
