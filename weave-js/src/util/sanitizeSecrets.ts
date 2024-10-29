const BAD_KEYS = ['api_key', 'auth_headers', 'Authorization'];

// Check for literal API key values in a string.
// Not comprehensive, but meant as a stopgap.
export const sanitizeString = (str: string): string => {
  for (const badKey of BAD_KEYS) {
    // Don't fire on non-literal key value, e.g. "api_key": api_key is OK
    const regex = new RegExp(`['"]${badKey}['"]:\\s+['"]`, 'i');
    if (regex.test(str)) {
      // Note: This is replacing the entire string which seemed like
      // the more cautious approach, we could also consider only
      // redacting the literal value.
      return `<Redacted: string contains ${badKey} pattern>`;
    }
  }
  return str;
};
