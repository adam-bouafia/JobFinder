/**
 * In-browser fuzzy match against the bundled sponsor snapshot.
 *
 * Deliberately NOT a port of rapidfuzz's WRatio - that scorer was found
 * (see jobfinder.sponsors.match, Python side) to give a false-positive
 * ~90/100 "match" to almost any short query against a long unrelated
 * candidate. This implements the same token_set_ratio semantics that
 * fixed it: compare word SETS, not substrings, so an informal/short name
 * that's genuinely a subset of the official name scores high, while an
 * unrelated short-vs-long pair does not. See matcher.test.ts for the
 * adversarial cases this is checked against (ported from the Python
 * regression tests).
 */

import { normalize } from "./normalize";

export interface Sponsor {
  kvk: string;
  name: string;
  name_normalized: string;
}

export interface SponsorSnapshot {
  generated_at: string;
  source: string;
  count: number;
  sponsors: Sponsor[];
}

export interface MatchResult {
  isSponsor: boolean;
  matchedName: string | null;
  kvk: string | null;
  score: number;
}

const DEFAULT_THRESHOLD = 90;

function levenshteinRatio(a: string, b: string): number {
  if (a === b) return 100;
  if (a.length === 0 || b.length === 0) return 0;

  const m = a.length;
  const n = b.length;
  const prevRow = new Array<number>(n + 1);
  for (let j = 0; j <= n; j++) prevRow[j] = j;

  for (let i = 1; i <= m; i++) {
    let prevDiag = prevRow[0];
    prevRow[0] = i;
    for (let j = 1; j <= n; j++) {
      const temp = prevRow[j];
      prevRow[j] =
        a[i - 1] === b[j - 1] ? prevDiag : 1 + Math.min(prevDiag, prevRow[j], prevRow[j - 1]);
      prevDiag = temp;
    }
  }

  const distance = prevRow[n];
  return (1 - distance / Math.max(m, n)) * 100;
}

function tokenSet(s: string): Set<string> {
  return new Set(s.split(/\s+/).filter(Boolean));
}

/** Word-set-based fuzzy ratio, 0-100. See module docstring for why. */
export function tokenSetRatio(a: string, b: string): number {
  const setA = tokenSet(a);
  const setB = tokenSet(b);
  const intersection = [...setA].filter((t) => setB.has(t)).sort();
  const onlyA = [...setA].filter((t) => !setB.has(t)).sort();
  const onlyB = [...setB].filter((t) => !setA.has(t)).sort();

  const t0 = intersection.join(" ");
  const t1 = [...intersection, ...onlyA].join(" ").trim();
  const t2 = [...intersection, ...onlyB].join(" ").trim();

  return Math.max(levenshteinRatio(t0, t1), levenshteinRatio(t0, t2), levenshteinRatio(t1, t2));
}

export class SponsorMatcher {
  private readonly sponsors: Sponsor[];

  constructor(snapshot: SponsorSnapshot) {
    this.sponsors = snapshot.sponsors;
  }

  match(companyName: string, threshold = DEFAULT_THRESHOLD): MatchResult {
    const query = normalize(companyName);
    let best: { sponsor: Sponsor; score: number } | null = null;

    for (const sponsor of this.sponsors) {
      const score = tokenSetRatio(query, sponsor.name_normalized);
      if (best === null || score > best.score) {
        best = { sponsor, score };
      }
    }

    if (best === null || best.score < threshold) {
      return { isSponsor: false, matchedName: null, kvk: null, score: best?.score ?? 0 };
    }

    return {
      isSponsor: true,
      matchedName: best.sponsor.name,
      kvk: best.sponsor.kvk,
      score: best.score,
    };
  }
}
