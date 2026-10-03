import { describe, expect, it } from "vitest";

import { normalize } from "../src/normalize";

describe("normalize", () => {
  it.each([
    ["Booking.com B.V.", "Booking.com"],
    ["@EasePay B.V.", "EasePay"],
    ["@Fentures B.V.", "Fentures"],
    ["ASML Holding N.V.", "ASML"],
    ["Coolblue B.V.", "coolblue"],
  ])("treats %s and %s as equal", (a, b) => {
    expect(normalize(a)).toBe(normalize(b));
  });

  it.each([
    "Booking.com B.V.",
    "@EasePay B.V.",
    "Aa-Dee Machinefabriek en Staalbouw Nederland B.V.",
  ])("is lowercase and trimmed for %s", (raw) => {
    const result = normalize(raw);
    expect(result).toBe(result.toLowerCase());
    expect(result).toBe(result.trim());
    expect(result).not.toBe("");
  });

  it("distinguishes different companies", () => {
    expect(normalize("Booking.com B.V.")).not.toBe(normalize("Adyen N.V."));
  });
});
