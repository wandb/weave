import _ from 'lodash';
import numeral from 'numeral';
import React from 'react';

import Markdown from '../components/Markdown';

export function isMarkdown(s: string): boolean {
  return s.startsWith('```') && s.endsWith('```') && s.length >= 6;
}

export function displayValueNoBarChart(
  value: any
): string | React.ReactElement<any> {
  if (
    _.isString(value) &&
    value.length &&
    value[0] === '{' &&
    value[value.length - 1] === '}'
  ) {
    try {
      value = JSON.parse(value);
    } catch (e) {
      // parse error; leave as a string.
    }
  }
  if (_.isNull(value) || _.isUndefined(value)) {
    return '-';
  } else if (typeof value === 'number') {
    if (_.isFinite(value)) {
      if (_.isInteger(value)) {
        return value.toString();
      } else {
        if (value < 1 && value > -1) {
          let s = value.toPrecision(4);
          if (!s.includes('e')) {
            while (s[s.length - 1] === '0') {
              s = s.slice(0, s.length - 1);
            }
          }
          return s;
        } else {
          return numeral(value).format('0.[000]');
        }
      }
    } else {
      return value.toString();
    }
  } else if (_.isString(value)) {
    // This could really bite you - with love from CVP (made more specific by Shawn)
    // TODO: This function should only return strings. Many callsites probably depend on
    // on that. We should have another displayValueHTML function that can return either a
    // string or a JSX element.
    if (value.match(/^(http|https|s3|gs|ftp):/)) {
      return React.createElement(
        'a',
        {href: value},
        value.substr(0, 25) + '...'
      );
    } else if (isMarkdown(value)) {
      return (
        <Markdown
          condensed={false}
          content={value.substring(3, value.length - 3)}
        />
      );
    } else {
      return value;
    }
  } else if (value._type) {
    if (value._type === 'images') {
      return 'Image';
    } else {
      return value._type;
    }
  } else {
    return JSON.stringify(value);
  }
}
