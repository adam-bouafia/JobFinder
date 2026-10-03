import { SponsorMatcher, type SponsorSnapshot } from "../matcher";
import { renderBadge } from "./overlay";
import { adapterForHostname } from "./site-adapters";

async function loadSnapshot(): Promise<SponsorSnapshot> {
  const url = chrome.runtime.getURL("src/data/sponsors.json");
  const response = await fetch(url);
  return (await response.json()) as SponsorSnapshot;
}

async function main(): Promise<void> {
  const adapter = adapterForHostname(window.location.hostname);
  if (!adapter) return;

  const snapshot = await loadSnapshot();
  const matcher = new SponsorMatcher(snapshot);
  const syncedAt = snapshot.generated_at;

  let lastCompanyText = "";

  function tick(): void {
    const el = adapter?.findCompanyElement();
    if (!el) return;
    const companyText = el.textContent?.trim() ?? "";
    if (!companyText || companyText === lastCompanyText) return;
    lastCompanyText = companyText;
    renderBadge(el, matcher.match(companyText), syncedAt);
  }

  tick();

  // LinkedIn/Indeed are SPAs: navigating between job listings doesn't
  // reload the page, so a MutationObserver (debounced) is what catches
  // subsequent job views, not just the initial injection.
  let debounceHandle: number | undefined;
  const observer = new MutationObserver(() => {
    if (debounceHandle !== undefined) return;
    debounceHandle = window.setTimeout(() => {
      debounceHandle = undefined;
      tick();
    }, 300);
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

main().catch((error: unknown) => {
  console.error("[JobFinder] failed to initialize:", error);
});
