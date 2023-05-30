// Because of inconsistent '%25' decoding behavior from the 'history' library,
// this function might be necessary to properly encode '%' as '%25' in a URI before decoding.

export function encodeURIPercentChar(str: string): string {
  return str.replace(/%(?![0-9A-F]{2})/g, '%25');
}

export const decodeURIComponentSafe = makeSafeURIFunction(decodeURIComponent);
type URIFunction = typeof encodeURI;

export function makeSafeURIFunction(fn: URIFunction): URIFunction {
  return (str: string) => {
    try {
      return fn(str);
    } catch {
      return str;
    }
  };
}

// The 'history' library specifically decodes '%25' into '%', while it leaves other
// special characters in their encoded forms. When we try to decode URIs on top of history's
// weird decoding, we run into errors because of the inconsistent special character decoding
// done by history.
// This is a dirty workaround that catches malformed URIs and manually encodes '%' into '%25',
// so that we can decode appropriately.
export function decodeURIComponentHistoryHax(str: string): string {
  try {
    return decodeURIComponent(str);
  } catch {
    const encodedStr = encodeURIPercentChar(str);
    return decodeURIComponentSafe(encodedStr);
  }
}

export function parseRunTabPath(pathStr?: string) {
  return pathStr == null || pathStr === ''
    ? []
    : pathStr.split('/').map(p => decodeURIComponentHistoryHax(p));
}

export function removeUrlProtocolPrefix(s: string) {
  return s.replace(/(^\w+:|^)\/\//, '');
}
