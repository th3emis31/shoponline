"use client";

import { useEffect } from "react";
import { captureCampaign } from "@/lib/client";

/** Credits orders to the ad that brought the visitor (see captureCampaign). Renders nothing. */
export default function CampaignCapture() {
  useEffect(() => { captureCampaign(window.location.search); }, []);
  return null;
}
