/**
 * Split a `data:` URL into (mimeType, payload). Payload is the raw string
 * after the comma — base64-encoded content is NOT decoded; it's passed
 * through as-is so the wire format matches what the producer embedded.
 * Returns `undefined` for non-data URLs.
 */
export function parseDataUrl(
  url: string
): {mimeType: string; payload: string} | undefined {
  if (!url.startsWith('data:')) return undefined;
  const rest = url.slice('data:'.length);
  const commaIdx = rest.indexOf(',');
  if (commaIdx < 0) return undefined;
  const header = rest.slice(0, commaIdx);
  const payload = rest.slice(commaIdx + 1);
  const semiIdx = header.indexOf(';');
  const mimeType = semiIdx >= 0 ? header.slice(0, semiIdx) : header;
  return {mimeType, payload};
}
