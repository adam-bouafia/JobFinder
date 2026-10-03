import type { SiteAdapter } from "../types";

/**
 * NOT verified against a live, logged-in LinkedIn session - deliberately
 * not scraped server-side to check (see docs/architecture.md's risk
 * posture: client-side-only is the point). LinkedIn's CSS classes churn
 * often, so the `/company/` href heuristic (a load-bearing URL pattern,
 * far more stable than styling classes) is tried as a fallback.
 *
 * If the badge doesn't appear on a real job page: open DevTools, inspect
 * the actual company-name element, and add its selector to the front of
 * CANDIDATE_SELECTORS. That's the only thing that should need to change.
 */
const CANDIDATE_SELECTORS = [
  ".job-details-jobs-unified-top-card__company-name a",
  ".job-details-jobs-unified-top-card__company-name",
  ".jobs-unified-top-card__company-name a",
  ".jobs-unified-top-card__company-name",
];

export const linkedinAdapter: SiteAdapter = {
  name: "linkedin",
  findCompanyElement(): HTMLElement | null {
    for (const selector of CANDIDATE_SELECTORS) {
      const el = document.querySelector<HTMLElement>(selector);
      if (el?.textContent?.trim()) return el;
    }
    const companyLink = document.querySelector<HTMLElement>('a[href*="/company/"]');
    if (companyLink?.textContent?.trim()) return companyLink;
    return null;
  },
};
