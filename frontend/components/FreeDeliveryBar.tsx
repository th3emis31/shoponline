import { formatGBP } from "@/lib/money";
import { site } from "@/lib/site";

export default function FreeDeliveryBar({ subtotal }: { subtotal: number }) {
  const target = site.freeShippingThreshold;
  const left = Math.max(target - subtotal, 0);
  const pct = Math.min(100, Math.round((subtotal / target) * 100));
  return (
    <div className="delivery-bar" data-testid="delivery-bar">
      <p>{left === 0 ? "You get free UK delivery." : `Add ${formatGBP(left)} more for free UK delivery.`}</p>
      <div className="bar" role="progressbar" aria-label="Progress to free delivery" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
        <span style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
