// Regular expressions for common Markdown syntax
// Note this is intentionally limited in scope to reduce false positives.
const LIKELY_MARKDOWN_PATTERNS: RegExp[] = [
  /```[\s\S]*```/, // Code block
  /\[.+\]\(.+\)/, // Links [text](url)
  /!\[.*\]\(.+\)/, // Images ![alt](url)
];

export const isLikelyMarkdown = (value: string): boolean => {
  return LIKELY_MARKDOWN_PATTERNS.some(pattern => pattern.test(value));
};
