import type { Product } from "./types";

// Server-side only: fetch straight from the backend.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new ApiError(`GET ${path} failed`, res.status);
  return res.json() as Promise<T>;
}

export async function getProducts(): Promise<Product[]> {
  return get<Product[]>("/api/products");
}

/** Returns null when the product does not exist (so the page can 404). */
export async function getProduct(id: string): Promise<Product | null> {
  try {
    return await get<Product>(`/api/products/${encodeURIComponent(id)}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}
