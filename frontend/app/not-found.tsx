import Link from "next/link";

export default function NotFound() {
  return (
    <>
      <h1>Page not found</h1>
      <p>That page doesn&apos;t exist. <Link href="/shop">Browse the collection</Link> instead.</p>
    </>
  );
}
