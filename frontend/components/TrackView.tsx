"use client";

import { useEffect } from "react";
import { track } from "@/lib/client";

export default function TrackView({ productId }: { productId: string }) {
  useEffect(() => {
    track("view_product", productId);
  }, [productId]);
  return null;
}
