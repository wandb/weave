import * as React from 'react';

import {fuzzyMatchHighlight, fuzzyMatchWithMapping} from './fuzzyMatch';

interface Matcher {
  match: <T>(
    objs: T[],
    matchStr: string | null,
    strFunc: (o: T) => string
  ) => T[];
  highlight: (
    str: string,
    query: string,
    matchStyle: {[key: string]: string}
  ) => React.ReactFragment;
}

// TODO(np): These other matchers just return matches in natural order
const FuzzyMatcher: Matcher = {
  match: fuzzyMatchWithMapping,
  highlight: fuzzyMatchHighlight,
};

const ExactMatcher: Matcher = {
  match(objs, matchStr, strFunc) {
    if (!matchStr) {
      return objs;
    }
    return objs
      .filter(o => strFunc(o).indexOf(matchStr) !== -1)
      .sort((a, b) => strFunc(a).localeCompare(strFunc(b)));
  },

  highlight(str, query, matchStyle) {
    const matchIndex = str.indexOf(query);
    if (matchIndex === -1) {
      return <span>{str}</span>;
    }

    const matchStart = matchIndex;
    const matchEnd = matchIndex + query.length;
    return renderHighlightSpans(str, matchStart, matchEnd, matchStyle);
  },
};

const RegexMatcher: Matcher = {
  match(objs, matchStr, strFunc) {
    if (!matchStr) {
      return objs;
    }
    let regex: RegExp | null = null;
    try {
      regex = new RegExp(matchStr);
    } catch (err) {
      return [];
    }
    return objs
      .filter(o => strFunc(o).match(regex!) != null)
      .sort((a, b) => strFunc(a).localeCompare(strFunc(b)));
  },
  highlight(str, query, matchStyle) {
    const match = str.match(new RegExp(query));
    if (match == null || match.length === 0) {
      return <span>{str}</span>;
    }

    const matchString = match[0];

    const matchStart = str.indexOf(matchString);
    const matchEnd = matchStart + matchString.length;
    return renderHighlightSpans(str, matchStart, matchEnd, matchStyle);
  },
};

function renderHighlightSpans(
  str: string,
  matchStart: number,
  matchEnd: number,
  matchStyle: {[key: string]: string}
) {
  return (
    <>
      <span key={0}>{str.substring(0, matchStart)}</span>
      <span key={1} className="fuzzy-match" style={matchStyle}>
        {str.substring(matchStart, matchEnd)}
      </span>
      <span key={2}>{str.substring(matchEnd)}</span>
    </>
  );
}

export type MatchMode = 'fuzzy' | 'exact' | 'regex';

const matchers: Record<MatchMode, Matcher> = {
  fuzzy: FuzzyMatcher,
  exact: ExactMatcher,
  regex: RegexMatcher,
} as const;

export function dynamicMatchWithMapping<T>(
  mode: MatchMode,
  objs: T[],
  matchStr: string | null,
  strFunc: (o: T) => string
): T[] {
  return matchers[mode].match(objs, matchStr, strFunc);
}

export function dynamicMatchHighlight(
  mode: MatchMode,
  str: string,
  query: string,
  matchStyle: {[key: string]: string} = {fontWeight: 'bold'}
): React.ReactFragment {
  return matchers[mode].highlight(str, query, matchStyle);
}
