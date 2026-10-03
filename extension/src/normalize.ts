/**
 * Normalize a company name for fuzzy matching against the sponsor register.
 *
 * Port of jobfinder.sponsors.normalize (Python). Keep these two in sync -
 * the whole point of bundling sponsors.json pre-normalized is that this
 * function and the Python one produce the same output for the same input.
 */

const LEGAL_SUFFIXES =
  /\b(b\.?v\.?|n\.?v\.?|holding|group|international|nederland|netherlands|europe|services|llc|llp|inc\.?|ltd\.?|gmbh)\b/gi;
const NON_ALNUM = /[^a-z0-9\s]/g;
const WHITESPACE = /\s+/g;
const LEADING_SYMBOLS = /^[@#* ]+/;

export function normalize(name: string): string {
  let text = name
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "") // strip combining diacritics (café -> cafe)
    .toLowerCase()
    .replace(LEADING_SYMBOLS, "");
  text = text.replace(LEGAL_SUFFIXES, " ");
  text = text.replace(NON_ALNUM, " ");
  text = text.replace(WHITESPACE, " ").trim();
  return text;
}
