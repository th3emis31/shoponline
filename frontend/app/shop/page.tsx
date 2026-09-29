import type { Metadata } from "next";
import Link from "next/link";
import ProductCard from "@/components/ProductCard";
import { getProducts } from "@/lib/api";
import { ROOMS, entry, isRoom } from "@/lib/catalog";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ room?: string }> };

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const { room } = await searchParams;
  return isRoom(room)
    ? { title: `Shop: ${ROOMS[room]}`, alternates: { canonical: `/shop?room=${room}` } }
    : { title: "Shop", alternates: { canonical: "/shop" } };
}

export default async function Shop({ searchParams }: Props) {
  const { room: raw } = await searchParams;
  const room = isRoom(raw) ? raw : undefined;
  const all = await getProducts();
  const inRoom = (id: string, r: string) => entry(id)?.rooms.includes(r as never) ?? false;
  const products = room ? all.filter((p) => inRoom(p.id, room)) : all;
  return (
    <>
      <h1>{room ? ROOMS[room] : "Shop all"}</h1>
      <nav className="chips" aria-label="Filter by room">
        <Link href="/shop" aria-current={!room ? "page" : undefined}>All ({all.length})</Link>
        {Object.entries(ROOMS).map(([id, label]) => {
          const n = all.filter((p) => inRoom(p.id, id)).length;
          return n > 0 ? (
            <Link key={id} href={`/shop?room=${id}`} aria-current={room === id ? "page" : undefined}>{label} ({n})</Link>
          ) : null;
        })}
      </nav>
      <p className="muted">All prices include VAT.</p>
      <div className="grid" data-testid="shop-grid">
        {products.map((p) => <ProductCard key={p.id} product={p} />)}
      </div>
      <p className="muted small">Not sure what you need? Read our <Link href="/guides">buying guides</Link>.</p>
    </>
  );
}
