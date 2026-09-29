import type { Metadata } from "next";

// Personal/transactional page: never index.
export const metadata: Metadata = { title: "Your cart", robots: { index: false, follow: false } };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
