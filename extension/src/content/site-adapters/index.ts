import type { SiteAdapter } from "../types";
import { indeedAdapter } from "./indeed";
import { linkedinAdapter } from "./linkedin";

/** Add a new job board by adding one file here and one line to this map. */
export function adapterForHostname(hostname: string): SiteAdapter | null {
  if (hostname.endsWith("linkedin.com")) return linkedinAdapter;
  if (hostname.endsWith("indeed.com") || hostname.endsWith("indeed.nl")) return indeedAdapter;
  return null;
}
