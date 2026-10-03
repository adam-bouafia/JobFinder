export interface SiteAdapter {
  name: string;
  /**
   * Finds the company-name element currently on the page, if any. Called
   * repeatedly (initial load + on DOM mutations) since LinkedIn/Indeed are
   * client-side-routed SPAs that don't reload on navigating between jobs.
   */
  findCompanyElement(): HTMLElement | null;
}
