import { describe, expect, it } from "vitest";
import { googleFeed, xml } from "@/lib/feed";

const site = { url: "https://shop.example", name: "NOVAHAUS", shippingFee: 395, freeShippingThreshold: 5000 };
const mat = { id: "desk-mat", name: "Desk Mat <90cm> & more", price: 3200, is_bundle: false, in_stock: true };
const riser = { id: "monitor-riser", name: "Riser", price: 5900, is_bundle: false, in_stock: false };
const copy = () => ({ tagline: "Calm.", problem: "", benefits: ["Soft"], included: [], verified: false, rooms: [] });

describe("google feed", () => {
  it("escapes XML", () => expect(xml(`a<b>&"c'`)).toBe("a&lt;b&gt;&amp;&quot;c&apos;"));
  it("includes only products with a real photo, with price, shipping and availability", () => {
    const out = googleFeed([mat, riser], copy, (id) => (id === "desk-mat" ? "/products/desk-mat.jpg" : null), site);
    expect(out).toContain("<g:id>desk-mat</g:id>");
    expect(out).toContain("<g:price>32.00 GBP</g:price>");
    expect(out).toContain("<g:price>3.95 GBP</g:price>"); // under the free-delivery threshold
    expect(out).toContain("<g:image_link>https://shop.example/products/desk-mat.jpg</g:image_link>");
    expect(out).toContain("Desk Mat &lt;90cm&gt; &amp; more");
    expect(out).not.toContain("<g:id>monitor-riser</g:id>");
    expect(out).toContain("real photo is added to public/products/: monitor-riser");
  });
  it("marks out-of-stock and free shipping", () => {
    const out = googleFeed([riser], copy, () => "/products/r.jpg", site);
    expect(out).toContain("<g:availability>out_of_stock</g:availability>");
    expect(out).toContain("<g:price>0.00 GBP</g:price>");
  });
});
