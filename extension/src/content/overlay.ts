import type { MatchResult } from "../matcher";

const BADGE_CLASS = "jobfinder-sponsor-badge";
const BADGE_ATTR = "data-jobfinder-badge";

const STYLE = `
  .${BADGE_CLASS} {
    display: inline-flex;
    align-items: center;
    margin-left: 8px;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    font-family: system-ui, sans-serif;
    vertical-align: middle;
    cursor: help;
  }
  .${BADGE_CLASS}--yes { background: #e6f4ea; color: #1e7e34; border: 1px solid #34a853; }
  .${BADGE_CLASS}--no { background: #f1f1f1; color: #5f6368; border: 1px solid #dadce0; }
`;

function ensureStyleInjected(): void {
  if (document.getElementById("jobfinder-style")) return;
  const style = document.createElement("style");
  style.id = "jobfinder-style";
  style.textContent = STYLE;
  document.head.appendChild(style);
}

/**
 * Renders (or replaces) the sponsor badge right after `anchor`. Idempotent
 * - safe to call repeatedly as the SPA re-renders the page.
 */
export function renderBadge(anchor: HTMLElement, result: MatchResult, syncedAt: string): void {
  ensureStyleInjected();

  const existing = anchor.parentElement?.querySelector(`[${BADGE_ATTR}]`);
  existing?.remove();

  const badge = document.createElement("span");
  badge.setAttribute(BADGE_ATTR, "true");
  badge.className = `${BADGE_CLASS} ${result.isSponsor ? `${BADGE_CLASS}--yes` : `${BADGE_CLASS}--no`}`;
  badge.textContent = result.isSponsor ? "IND recognised sponsor" : "Not an IND sponsor";
  badge.title = result.isSponsor
    ? `KVK ${result.kvk ?? "?"} - match score ${result.score.toFixed(0)} - synced ${syncedAt} - verify at ind.nl`
    : `Best score ${result.score.toFixed(0)} - synced ${syncedAt} - verify at ind.nl before relying on this`;

  anchor.insertAdjacentElement("afterend", badge);
}
