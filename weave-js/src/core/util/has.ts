/**
 * A type guard. Checks if given object x has the key.
 */
export const has = <K extends string>(
  p: K,
  x: unknown
): x is {[key in K]: unknown} => typeof x === 'object' && x != null && p in x;
