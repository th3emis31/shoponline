import type { Metadata } from "next";
import Link from "next/link";
import { formatGBP } from "@/lib/money";
import { site } from "@/lib/site";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: { default: `${site.name} — ${site.tagline}`, template: `%s · ${site.name}` },
  description: "Calm, well-made organisation pieces for small UK homes and home offices.",
  openGraph: { siteName: site.name, locale: "en_GB", type: "website" },
  // Preview site: keep every page out of search results until launch.
  robots: site.launchReady ? undefined : { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB">
      <body>
        {!site.launchReady && (
          <div className="draft-banner" role="note">
            Preview site — not yet taking real orders.
          </div>
        )}
        <div className="announcement">
          Free UK delivery over {formatGBP(site.freeShippingThreshold)} · {site.returnDays}-day returns
        </div>
        <header className="site">
          <div className="container">
            <Link href="/" className="brand">{site.name}</Link>
            <nav className="main" aria-label="Main">
              <Link href="/shop">Shop</Link>
              <Link href="/about">About</Link>
              <Link href="/faq">FAQ</Link>
              <Link href="/track">Track order</Link>
              <Link href="/cart">Cart</Link>
            </nav>
          </div>
        </header>
        <main>
          <div className="container">{children}</div>
        </main>
        <footer className="site">
          <div className="container cols">
            <div>
              <strong>{site.name}</strong>
              <p>{site.tagline}</p>
            </div>
            <div>
              <Link href="/shop">Shop</Link>
              <Link href="/about">About</Link>
              <Link href="/contact">Contact</Link>
              <Link href="/faq">FAQ</Link>
            </div>
            <div>
              <Link href="/shipping">Shipping</Link>
              <Link href="/returns">Returns</Link>
              <Link href="/track">Track order</Link>
            </div>
            <div>
              <Link href="/privacy">Privacy</Link>
              <Link href="/terms">Terms</Link>
              <Link href="/cookies">Cookies</Link>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
