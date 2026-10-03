import type { SiteAdapter } from "../types";

/**
 * Same caveat as linkedin.ts: not verified against a live page. Indeed has
 * historically used `data-testid` attributes for key elements, which tend
 * to be more stable than styling classes, so those are tried first.
 */
const CANDIDATE_SELECTORS = [
  '[data-testid="inline-company-name"]',
  '[data-company-name="true"]',
  ".jobsearch-CompanyInfoContainer a",
  ".jobsearch-InlineCompanyRating a",
];

export const indeedAdapter: SiteAdapter = {
  name: "indeed",
  findCompanyElement(): HTMLElement | null {
    for (const selector of CANDIDATE_SELECTORS) {
      const el = document.querySelector<HTMLElement>(selector);
      if (el?.textContent?.trim()) return el;
    }
    return null;
  },
};
