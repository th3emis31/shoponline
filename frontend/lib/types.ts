export type Product = {
  id: string;
  name: string;
  price: number; // pence, inc. VAT
  is_bundle: boolean;
  in_stock: boolean;
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
  status: "placed" | "pending_payment" | "paid" | "cancelled" | "payment_review";
  created_at: string;
  checkout_url?: string | null;
};
