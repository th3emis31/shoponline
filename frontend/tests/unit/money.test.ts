import { describe, expect, it } from "vitest";
import { formatGBP } from "@/lib/money";

describe("formatGBP", () => {
  it("formats pence as pounds", () => {
    expect(formatGBP(3200)).toBe("£32.00");
    expect(formatGBP(395)).toBe("£3.95");
    expect(formatGBP(0)).toBe("£0.00");
    expect(formatGBP(-556)).toBe("-£5.56");
  });
  it("never renders NaN", () => {
    expect(formatGBP(Number.NaN)).toBe("—");
  });
});
