export type Product = {
  id: string;
  name: string;
  price: number; // pence, inc. VAT
  is_bundle: boolean;
  in_stock: boolean;
  delivery_estimate?: string | null;
};

export type CartLine = {
  product_id: string;
  name: string;
  unit_price: number;
  quantity: number;
  line_total: number;
};

export type Cart = {
  id: string;
  items: CartLine[];
  subtotal: number;
  shipping: number;
  total: number;
};

export type Order = Cart & {
  status: "placed" | "pending_payment" | "paid" | "shipped" | "cancelled" | "payment_review";
  created_at: string;
  checkout_url?: string | null;
  review_path?: string | null;
};

export type Review = { id: number; rating: number; title: string; body: string; name: string; date: string; verified: boolean };
export type ReviewSummary = { count: number; average: number | null; reviews: Review[] };
