import LRUCache from 'lru-cache';

// This function is called in the opPick resolver, for the key passed to op
// opPick. opPick tends to be called many times with the same key, for example
// with filter and groupBy operations. So we manually memoize this function here,
// but bound cached results to 8MB
const splitEscapedStringCache = new LRUCache<string, string[]>({
  max: 1048576 * 8,
  length: val => {
    return val.reduce((len, el) => {
      return len + el.length;
    }, 0);
  },
  updateAgeOnGet: true,
});

export const splitEscapedString = (s: string) => {
  const cached = splitEscapedStringCache.get(s);
  if (typeof cached !== 'undefined') {
    return cached;
  }

  const placeholder = '__wb_escaped_sep__';
  const result = s
    .replace(new RegExp('\\\\\\.', 'g'), placeholder)
    .split('.')
    .map(is => is.replace(new RegExp(placeholder, 'g'), '.'));
  splitEscapedStringCache.set(s, result);
  return result;
};
