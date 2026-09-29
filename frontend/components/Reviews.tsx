import type { ReviewSummary } from "@/lib/types";

const stars = (n: number) => "★★★★★".slice(0, Math.round(n)) + "☆☆☆☆☆".slice(0, 5 - Math.round(n));

/** Verified-buyer reviews. Renders nothing until at least one real review is published. */
export default function Reviews({ data }: { data: ReviewSummary | null }) {
  if (!data || data.count === 0) return null;
  return (
    <section data-testid="reviews">
      <h2>Reviews</h2>
      <p>
        <span aria-hidden="true" className="stars-shown">{stars(data.average ?? 0)}</span>{" "}
        <strong>{data.average?.toFixed(1)} out of 5</strong>{" "}
        <span className="muted">from {data.count} verified buyer{data.count === 1 ? "" : "s"}</span>
      </p>
      <ul className="review-list">
        {data.reviews.map((r) => (
          <li key={r.id}>
            <span aria-label={`${r.rating} out of 5 stars`} className="stars-shown">{stars(r.rating)}</span>
            {r.title && <strong> {r.title}</strong>}
            {r.body && <p>{r.body}</p>}
            <p className="muted small">
              {r.name} · Verified buyer · {new Date(r.date).toLocaleDateString("en-GB", { month: "long", year: "numeric" })}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
