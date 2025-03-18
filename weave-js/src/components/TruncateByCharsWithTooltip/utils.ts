export type TruncatedPart = 'start' | 'middle' | 'end';

/**
 * Accepts some text and truncates it to the maxChars specified.
 * If text is shorter than maxChars, it will be returned as-is.
 * Text may be truncated at the start, middle, or end (e.g.
 * "…lo world", "hell…orld", or "hello wo…")
 */
export const truncateTextByChars = (
  text: string,
  maxChars: number,
  truncatedPart: TruncatedPart
): string => {
  if (text.length <= maxChars) {
    return text;
  }

  if (truncatedPart === 'start') {
    return '\u2026' + text.slice(-maxChars);
  }

  if (truncatedPart === 'middle') {
    const numStartChars = Math.ceil(maxChars / 2);
    const numEndChars = Math.floor(maxChars / 2);
    return text.slice(0, numStartChars) + '\u2026' + text.slice(-numEndChars);
  }

  if (truncatedPart === 'end') {
    return text.slice(0, maxChars) + '\u2026';
  }

  // should never reach here but typescript is being silly
  return text;
};
