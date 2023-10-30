/**
 * Utilities for formatting numbers. These are inspired by Python's format specifier mini-language.
 */
import numeral from 'numeral';

import {trimEndChar} from './string';

const FORMAT_NUMBER = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  useGrouping: true,
});

const FORMAT_PERCENT = new Intl.NumberFormat('en-US', {
  style: 'percent',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  useGrouping: false,
});

const FORMAT_COMPACT = new Intl.NumberFormat('en-US', {
  notation: 'compact',
});

export const NON_CUSTOM_FORMATS = [
  'Automatic',
  'Number',
  'Percent',
  'Scientific',
  'Compact',
];

type CurrencyFormat = {
  locale: string;
  currency: string;
};
const CURRENCY_FORMATS: Record<string, CurrencyFormat> = {
  USD: {
    locale: 'en-US',
    currency: 'USD',
  },
  // TODO: Support other currencies
};

// See https://docs.python.org/3/library/string.html#format-specification-mini-language
// format_spec     ::=  [[fill]align][sign]["z"]["#"]["0"][width][grouping_option]["." precision][type]
// fill            ::=  <any character>
// align           ::=  "<" | ">" | "=" | "^"
// sign            ::=  "+" | "-" | " "
// width           ::=  digit+
// grouping_option ::=  "_" | ","
// precision       ::=  digit+
// type            ::=  "b" | "c" | "d" | "e" | "E" | "f" | "F" | "g" | "G" | "n" | "o" | "s" | "x" | "X" | "%"
// TODO: Handle fill/align, underscore grouping option, more types
// TODO: Handle 'z' - coerce negative zero floating-point values to positive zero
//       after rounding to the format precision.
// TODO: Handle '#' - use "alternate form" for the conversion
// TODO: Consider using something like https://keleshev.com/verbose-regular-expressions-in-javascript
const FORMAT_SPEC_SIGN = '([\\+\\- ]?)';
const FORMAT_SPEC_WIDTH = '(\\d*)';
const FORMAT_SPEC_GROUPING_OPTION = '([_,]?)';
const FORMAT_SPEC_PRECISION = '(?:\\.(\\d+))?';
const FORMAT_SPEC_TYPE = '([bcdeEfFgGnosxX%]?)';

const RE_FORMAT_SPEC = new RegExp(
  `${FORMAT_SPEC_SIGN}(0?)${FORMAT_SPEC_WIDTH}${FORMAT_SPEC_GROUPING_OPTION}${FORMAT_SPEC_PRECISION}${FORMAT_SPEC_TYPE}`
);

const insertAt = (str: string, index: number, insert: string): string => {
  return str.slice(0, index) + insert + str.slice(index);
};

export const formatNumber = (n: number, format: string): string => {
  if (format === 'Automatic') {
    // Use the same logic as displayValueNoBarChart
    if (!Number.isFinite(n) || Number.isInteger(n)) {
      return n.toString();
    }
    if (-1 < n && n < 1) {
      let s = n.toPrecision(4);
      if (!s.includes('e')) {
        s = trimEndChar(s, '0');
      }
      return s;
    }
    return numeral(n).format('0.[000]');
  }
  if (format === 'Number') {
    return FORMAT_NUMBER.format(n);
  }
  if (format === 'Percent') {
    return FORMAT_PERCENT.format(n);
  }
  if (format === 'Scientific') {
    return formatNumber(n, '*.6e');
  }
  if (format === 'Compact') {
    if (Number.isFinite(n) && Math.abs(n) >= 1e15) {
      // Output like 1,234,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000,000T
      // is not actually very "compact"; just use scientific notation instead.
      return formatNumber(n, '*.2e');
    }
    return FORMAT_COMPACT.format(n);
  }
  if (format.startsWith('$')) {
    const currencyFormat = CURRENCY_FORMATS[format.substring(1)];
    if (currencyFormat) {
      const numberFormat = new Intl.NumberFormat(currencyFormat.locale, {
        style: 'currency',
        currency: currencyFormat.currency,
      });
      return numberFormat.format(n);
    }
  }
  if (format.startsWith('*')) {
    if (!Number.isFinite(n)) {
      return n.toLocaleString();
    }

    const match = RE_FORMAT_SPEC.exec(format.substring(1));
    if (match) {
      const [sign, zero, width, grouping, precision, type] = match.slice(1);

      const defaultType = Number.isInteger(n) ? 'd' : 'f';
      const resolvedType = type === '' ? defaultType : type;
      const notation = ['e', 'E'].includes(resolvedType)
        ? 'scientific'
        : 'standard';

      const resolvedWidth = width !== '' ? parseInt(width, 10) : undefined;
      const useGrouping = grouping === ',';

      const minimumFractionDigits =
        precision != null
          ? parseInt(precision, 10)
          : ['e', 'E', 'f'].includes(resolvedType)
          ? 6
          : 0;
      const maximumFractionDigits = minimumFractionDigits;

      const signDisplay = sign === '+' ? 'always' : 'auto';
      let prefix = '';
      if (n > 0 && sign === ' ') {
        prefix = ' ';
      }

      const options: Intl.NumberFormatOptions = {
        notation,
        useGrouping,
        minimumFractionDigits,
        maximumFractionDigits,
        signDisplay,
      };

      const numberFormat = new Intl.NumberFormat('en-US', options);
      let formatted = prefix + numberFormat.format(n);

      if (['e', 'E'].includes(resolvedType)) {
        const [coefficient, exponent] = formatted.split('E');
        const resolvedExponent = parseInt(exponent, 10);
        const esign = resolvedExponent >= 0 ? '+' : ''; // Negative has sign included
        let exponentStr = exponent;
        if (Math.abs(resolvedExponent) < 10) {
          // Insert a zero
          const index = exponentStr.startsWith('-') ? 1 : 0;
          exponentStr = insertAt(exponentStr, index, '0');
        }
        formatted = `${coefficient}${resolvedType}${esign}${exponentStr}`;
      }

      if (resolvedWidth != null) {
        const diff = resolvedWidth - formatted.length;
        if (diff > 0) {
          // Padding char gets inserted after the sign
          const paddingChar = zero !== '' ? '0' : ' ';
          const index = ['+', '-', ' '].includes(formatted[0]) ? 1 : 0;
          return insertAt(formatted, index, paddingChar.repeat(diff));
        }
      }
      return formatted;
    }
  }
  return n.toString();
};
