/**
 * Buying guides (Blueprint section H). Written to help people choose, not to push:
 * no invented statistics. General advice cites its source (e.g. HSE guidance).
 */
export type Guide = { slug: string; title: string; summary: string; products: string[]; body: { h?: string; p?: string; list?: string[] }[] };

export const guides: Guide[] = [
  {
    slug: "hide-desk-cables-without-drilling",
    title: "How to hide desk cables without drilling",
    summary: "A renter-friendly way to get chargers and extension leads off the floor, in about ten minutes.",
    products: ["cable-tray", "cable-clips"],
    body: [
      { p: "Most cable mess comes from three things: the extension lead on the floor, cables that are too long, and chargers that fall behind the desk. You can fix all three without a single hole." },
      { h: "1. Lift the extension lead" },
      { p: "Put the extension lead in an under-desk tray that clamps onto the desk edge. Check your desk thickness first: clamp trays only fit a certain range, which the fit guide lists." },
      { h: "2. Coil the spare length" },
      { p: "Loop the extra length of each cable loosely and lay it in the tray. Don't wrap cables tightly around power adapters; a loose loop is kinder to the cable." },
      { h: "3. Keep the ones you use on top" },
      { p: "Phone and laptop chargers you plug in daily should stay on the desk. A weighted cable clip stops them sliding off the back." },
      { h: "Safety" },
      { list: ["Don't daisy-chain extension leads.", "Keep the tray clear of heaters.", "Leave some slack, so nothing is pulled tight when you move the desk."] },
    ],
  },
  {
    slug: "choosing-a-desk-mat",
    title: "Choosing a desk mat: size and material",
    summary: "How big a desk mat should be, and the difference between felt, leather-look and cloth.",
    products: ["desk-mat"],
    body: [
      { h: "Size" },
      { p: "Measure the space your keyboard and mouse use together, then add a few centimetres on each side. For most people that's around 80 to 90 cm wide. On a small desk (100 to 120 cm), a 90 × 40 cm mat leaves room for a lamp or a notebook." },
      { h: "Material" },
      { list: ["Felt: warm, quiet and soft, but it shows spills.", "Vegan leather: wipes clean and feels smooth; it can feel cool in winter.", "Two-sided mats (felt one side, leather-look the other) let you switch."] },
      { h: "Check before you buy" },
      { p: "Look for stitched or sealed edges, which are less likely to curl or fray, and a non-slip underside." },
    ],
  },
  {
    slug: "monitor-height-small-desk",
    title: "Getting your screen to the right height on a small desk",
    summary: "Simple checks from UK workplace guidance, and how a riser helps on a compact desk.",
    products: ["monitor-riser", "desk-reset"],
    body: [
      { p: "UK Health and Safety Executive (HSE) guidance on display screen equipment suggests positioning the screen so it's comfortable to look at without bending your neck. A common check is to have the top of the screen roughly at eye level, about an arm's length away." },
      { h: "Quick check" },
      { list: ["Sit back normally.", "Look straight ahead: your eyes should land near the top of the screen.", "If you look down at the middle of the screen, it's probably too low."] },
      { h: "On a small desk" },
      { p: "A riser lifts the screen and gives back the space underneath: a drawer or a shelf for things that otherwise clutter the desk." },
      { p: "If you use a laptop all day, a separate keyboard and a raised laptop are usually more comfortable than a laptop flat on the desk." },
    ],
  },
];

export function guide(slug: string): Guide | undefined {
  return guides.find((g) => g.slug === slug);
}
