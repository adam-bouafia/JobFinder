import { describe, expect, it } from "vitest";

import { normalize } from "../src/normalize";
import { SponsorMatcher, type SponsorSnapshot, tokenSetRatio } from "../src/matcher";

function snapshotFrom(entries: Array<[kvk: string, name: string]>): SponsorSnapshot {
  return {
    generated_at: "2026-10-01T00:00:00Z",
    source: "test-fixture",
    count: entries.length,
    sponsors: entries.map(([kvk, name]) => ({
      kvk,
      name,
      name_normalized: normalize(name),
    })),
  };
}

describe("tokenSetRatio", () => {
  it.each([
    ["easepay", "easepay", 100],
    ["ing", "ing bank", 100],
    ["asml", "asml netherlands", 100],
  ])("scores %s vs %s at %i", (a, b, expected) => {
    expect(tokenSetRatio(a, b)).toBe(expected);
  });

  it.each([
    // Regression: the Python matcher's original WRatio scorer gave these
    // a false-positive ~90.0 (it degrades to partial_ratio * 0.9, trivially
    // satisfied by any short query against a long candidate). The fix was
    // switching to token_set_ratio; this locks the same fix in here.
    ["adien", "joulz infradiensten"],
    ["jansen fietsenwinkel zoetermeer", "wink"],
  ])("keeps %s vs %s well under the match threshold", (a, b) => {
    expect(tokenSetRatio(a, b)).toBeLessThan(90);
  });
});

describe("SponsorMatcher", () => {
  const matcher = new SponsorMatcher(
    snapshotFrom([
      ["31047344", "Booking.com B.V."],
      ["83892869", "@EasePay B.V."],
      ["17052456", "ASML Netherlands B.V."],
      ["62280708", "Joulz Infradiensten B.V."],
      ["30132076", "Wink B.V."],
    ]),
  );

  it("finds a match despite a legal suffix", () => {
    const result = matcher.match("Booking.com");
    expect(result.isSponsor).toBe(true);
    expect(result.kvk).toBe("31047344");
  });

  it("finds a match despite a stray leading symbol in the source data", () => {
    const result = matcher.match("EasePay");
    expect(result.isSponsor).toBe(true);
    expect(result.kvk).toBe("83892869");
  });

  it("finds an abbreviated official name", () => {
    const result = matcher.match("ASML");
    expect(result.isSponsor).toBe(true);
    expect(result.kvk).toBe("17052456");
  });

  it("rejects an unrelated name", () => {
    const result = matcher.match("Totally Unrelated Bakery XYZ");
    expect(result.isSponsor).toBe(false);
  });

  it.each(["Adien", "Jansen Fietsenwinkel Zoetermeer"])(
    "rejects the short-query-vs-long-candidate false positive for %s",
    (query) => {
      const result = matcher.match(query);
      expect(result.isSponsor).toBe(false);
    },
  );
});
