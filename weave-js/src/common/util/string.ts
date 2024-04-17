import StringUtil from 'lodash';

// Splits a string on the first occurrence of delim. If delim isn't present, returns [s, null]
export function splitOnce(s: string, delim: string): [string, string | null] {
  const delimLoc = StringUtil.indexOf(s, delim);
  if (delimLoc === -1) {
    return [s, null];
  }
  return [s.slice(0, delimLoc), s.slice(delimLoc + 1)];
}

export function splitOnceLast(
  s: string,
  delim: string
): [string, string] | [null, null] {
  const delimLoc = StringUtil.lastIndexOf(s, delim);
  if (delimLoc === -1) {
    return [null, null];
  }
  return [s.slice(0, delimLoc), s.slice(delimLoc + 1)];
}

export function stripQuotesAndSpace(s: any) {
  if (typeof s === 'string') {
    return s.replace(/^["\s]+|["\s]+$/g, '');
  } else {
    return s;
  }
}

/**
 * Replaces all special characters with '__'. The GQL spec only allows letters, numbers, and underscores.
 * Spec: https://spec.graphql.org/June2018/#sec-Names
 */
export function sanitizeGQLAlias(s: string): string {
  return s.replace(/\W+/g, '__');
}

export function capitalizeFirst(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

export function isValidEmail(s: string) {
  return /(.+)@(.+){2,}\.(.+){2,}/.test(s);
}

export function removeNonASCII(str: string): string {
  // eslint-disable-next-line no-control-regex
  return str.replace(/[^\x00-\x7F]/g, '');
}

export function indent(s: string, level: number) {
  let result = '';
  for (let i = 0; i < level; i++) {
    result += '  ';
  }
  return result + s;
}

export function applyPrefixIfNeeded(prefix: string, str: string): string {
  if (str.startsWith(prefix)) {
    return str;
  }
  return prefix + str;
}

export function stripPrefixesIfNeeded(prefixes: string[], str: string): string {
  for (const prefix of prefixes) {
    if (str.startsWith(prefix)) {
      return str.slice(prefix.length);
    }
  }
  return str;
}

export function replaceDashWithSpace(s: string): string {
  return s.replace(/-/g, ' ');
}
