import { defineManifest } from "@crxjs/vite-plugin";

import pkg from "./package.json";

export default defineManifest({
  manifest_version: 3,
  name: "JobFinder: IND Sponsor Badge",
  description:
    "Shows whether a company on LinkedIn/Indeed is an IND recognised sponsor (NL work-visa sponsorship).",
  version: pkg.version,
  content_scripts: [
    {
      matches: ["*://*.linkedin.com/*", "*://*.indeed.com/*", "*://*.indeed.nl/*"],
      js: ["src/content/main.ts"],
      run_at: "document_idle",
    },
  ],
  web_accessible_resources: [
    {
      resources: ["src/data/sponsors.json"],
      matches: ["*://*.linkedin.com/*", "*://*.indeed.com/*", "*://*.indeed.nl/*"],
    },
  ],
});
