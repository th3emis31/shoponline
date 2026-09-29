/**
 * Shop copy for each product, written from the NOVAHAUS Blueprint (sections C, E, G).
 * Honesty rule: benefits describe the DESIGN INTENT. Exact dimensions, materials and
 * load ratings are only published once measured on the approved sample
 * (`verified: true`). Until then the page says so.
 */
export type CatalogEntry = {
  tagline: string;
  problem: string;
  benefits: string[];
  included: string[];
  verified: boolean;
  /** Rooms it's designed for (shop "filter by room"). */
  rooms: RoomId[];
};

export const ROOMS = {
  "home-office": "Home office",
  "living-room": "Living room",
  bedroom: "Bedroom",
} as const;
export type RoomId = keyof typeof ROOMS;

export const BUNDLE_PARTS = ["desk-mat", "cable-tray", "cable-clips"] as const;
export const BUNDLE_ID = "desk-reset";

export const catalog: Record<string, CatalogEntry> = {
  "desk-mat": {
    tagline: "A calm, soft surface that protects your desk.",
    problem: "Scratched desk, cold hands, a setup that never quite looks finished.",
    benefits: [
      "Two materials: warm felt on top, grippy vegan-leather underneath",
      "Stitched edges designed not to curl or fray",
      "Big enough for keyboard and mouse together (90 × 40 cm)",
    ],
    included: ["1 desk mat, 90 × 40 cm"],
    verified: false,
    rooms: ["home-office"],
  },
  "cable-tray": {
    tagline: "Hide the cable mess under your desk, with no drilling.",
    problem: "Chargers and extension leads hanging under the desk, and you rent so you can't drill.",
    benefits: [
      "Clamps on, so there are no holes (renter-friendly)",
      "Steel tray holds an extension lead and spare cable",
      "Powder-coated finish in muted colours",
    ],
    included: ["1 steel cable tray", "2 clamps", "Fit guide for desk thickness"],
    verified: false,
    rooms: ["home-office", "living-room"],
  },
  "cable-clips": {
    tagline: "Chargers stay where you left them.",
    problem: "Cables slide off the desk and fall behind it every day.",
    benefits: [
      "Real walnut with a soft silicone grip",
      "Weighted, so the cable stays put",
      "Matches the rest of the Desk Reset set",
    ],
    included: ["Set of cable clips"],
    verified: false,
    rooms: ["home-office", "living-room", "bedroom"],
  },
  "monitor-riser": {
    tagline: "Screen at eye level, clutter in the drawer.",
    problem: "A screen that's too low, and small things everywhere.",
    benefits: [
      "Solid oak, designed to lift your screen closer to eye level",
      "Hidden drawer for pens, cables and keys",
      "Rear cable cut-out keeps the desk tidy",
    ],
    included: ["1 oak monitor riser with drawer"],
    verified: false,
    rooms: ["home-office"],
  },
  "desk-reset": {
    tagline: "Everything for a tidy desk, in one parcel.",
    problem: "Messy cables, a scratched desk and chargers that keep falling. Fixed together.",
    benefits: [
      "Felt + vegan-leather desk mat",
      "No-drill under-desk cable tray",
      "Walnut cable clips",
      "One parcel, designed to be used together",
    ],
    included: ["1 desk mat", "1 cable tray with clamps", "Set of cable clips"],
    verified: false,
    rooms: ["home-office"],
  },
};

export function entry(id: string): CatalogEntry | undefined {
  return catalog[id];
}

export function isRoom(value: string | undefined): value is RoomId {
  return !!value && Object.prototype.hasOwnProperty.call(ROOMS, value);
}
