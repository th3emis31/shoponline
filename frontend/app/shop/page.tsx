import type { Metadata } from "next";
import ProductCard from "@/components/ProductCard";
import { getProducts } from "@/lib/api";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Shop" };

export default async function Shop() {
  const products = await getProducts();
  return (
    <>
      <h1>Home office</h1>
      <p className="muted">All prices include VAT.</p>
      <div className="grid">
        {products.map((p) => <ProductCard key={p.id} product={p} />)}
      </div>
    </>
  );
}
