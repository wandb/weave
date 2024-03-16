import _ from 'lodash';
import React, {CSSProperties, useCallback, useState} from 'react';
import {
  Link as RRLink,
  LinkProps as RRLinkProps,
  NavLink as RRNavLink,
  NavLinkProps as RRNavLinkProps,
} from 'react-router-dom';
import styled from 'styled-components';

import getConfig from '../../config';
import {TEAL_500, TEAL_600} from '../css/color.styles';
import {FCWithRef} from './types';

const URL_REGEXP = /https?:\/\/[^\s]+/g;
const MD_LINK_REGEXP = /\[[^\]]+\]\(https?:\/\/[^)\s]+\)/g;

// Given a string that might have URLs in it, returns an array
// where each element is a portion of the original string or a
// JSX element containing one of the links, with the original ordering
// preserved.
// For example, this input: "See my website at http://mywebsite.com and leave a comment!"
// would yield the following output: ['See my website at ', <a href.../>, ' and leave a comment!']
/* eslint-disable wandb/no-a-tags */
export function linkify(
  text: string,
  props: JSX.IntrinsicElements['a']
): Array<string | JSX.Element> {
  const parts = linkifyWithRegex(text, props, MD_LINK_REGEXP, (m, i) => {
    const descEnd = m.indexOf(']');
    const desc = m.slice(1, descEnd);
    const href = m.slice(descEnd + 2, m.length - 1);
    return (
      <a key={`${href}-${i}`} href={href} {...props}>
        {desc}
      </a>
    );
  });
  return _.flatten(
    parts.map(p => {
      if (typeof p !== 'string') {
        return p;
      }
      return linkifyWithRegex(p, props, URL_REGEXP, (m, i) => (
        <a key={`${m}-${i}`} href={m} {...props}>
          {m}
        </a>
      ));
    })
  );
}
/* eslint-enable wandb/no-a-tags */

function linkifyWithRegex(
  text: string,
  props: JSX.IntrinsicElements['a'],
  r: RegExp,
  getLinkFromMatch: (m: string, i: number) => JSX.Element
): Array<string | JSX.Element> {
  const matches = text.match(r) ?? [];
  const elems: Array<string | JSX.Element> = [text];
  matches.forEach((match, i) => {
    const remainingStr = elems.pop();
    if (remainingStr == null || !_.isString(remainingStr)) {
      // This is mostly a typeguard. This shouldn't happen.
      throw new Error('Exception encountered when linkifying text.');
    }

    const startIdx = remainingStr.indexOf(match);
    const endIdx = startIdx + match.length;
    const firstHalf = remainingStr.slice(0, startIdx);
    const secondHalf = remainingStr.slice(endIdx);
    if (!_.isEmpty(firstHalf)) {
      elems.push(firstHalf);
    }
    elems.push(getLinkFromMatch(match, i));
    if (!_.isEmpty(secondHalf)) {
      elems.push(secondHalf);
    }
  });
  return elems;
}

export const A = styled.a`
  font-weight: 600;
  color: ${TEAL_600};
  &:hover {
    color: ${TEAL_500};
  }
`;
A.displayName = 'S.A';

export const TargetBlank: FCWithRef<
  React.AnchorHTMLAttributes<HTMLAnchorElement>,
  HTMLAnchorElement
> = React.memo(
  React.forwardRef(({children, ...passthroughProps}, ref) => {
    // Enforce an absolute prefixed url for blank targets
    if (
      passthroughProps.href != null &&
      !(passthroughProps.href.indexOf('://') > 0) // regex for http, file, s3, gs, etc
    ) {
      passthroughProps.href = getConfig().urlPrefixed(passthroughProps.href);
    }
    return (
      // eslint-disable-next-line wandb/no-a-tags
      <A
        target="_blank"
        rel="noopener noreferrer"
        {...passthroughProps}
        ref={ref}>
        {children}
      </A>
    );
  })
);

export type LinkProps = RRLinkProps & {
  RRLinkComp?: React.FC<any>;
  newTab?: boolean;
};

export const Link: FCWithRef<LinkProps, HTMLAnchorElement> = React.memo(
  React.forwardRef(
    ({RRLinkComp = RRLink, newTab = true, children, ...passProps}, ref) => {
      const {to} = passProps;
      const isExternalLink =
        typeof to === 'string' &&
        (to.startsWith('http') || to.startsWith('//'));
      return isExternalLink ? (
        newTab ? (
          <TargetBlank {...passProps} href={to} ref={ref}>
            {children}
          </TargetBlank>
        ) : (
          // eslint-disable-next-line wandb/no-a-tags
          <a {...passProps} href={to} ref={ref}>
            {children}
          </a>
        )
      ) : (
        <RRLinkComp {...passProps} ref={ref}>
          {children}
        </RRLinkComp>
      );
    }
  )
);

type NavLinkProps = Omit<RRNavLinkProps, 'className' | 'style'> & {
  className?: string;
  style?: CSSProperties;
};

export const NavLink: React.FC<NavLinkProps> = React.memo(props => {
  return <Link RRLinkComp={RRNavLink} {...props} />;
});

type LinkNoCrawlProps = LinkProps & {LinkComp?: React.FC<any>};

export const LinkNoCrawl: React.FC<LinkNoCrawlProps> = React.memo(
  ({LinkComp = Link, ...passProps}) => {
    const [active, setActive] = useState(false);
    const activate = useCallback(() => setActive(true), []);

    if (!active) {
      const {className, style, children} = passProps;
      return (
        // eslint-disable-next-line jsx-a11y/anchor-is-valid
        <a
          className={className}
          style={style}
          data-test={(passProps as any)['data-test']}
          onMouseEnter={activate}
          onTouchStart={activate}>
          {children}
        </a>
      );
    }

    return <LinkComp {...passProps} />;
  }
);

export const NavLinkNoCrawl: React.FC<NavLinkProps> = React.memo(props => {
  return <LinkNoCrawl LinkComp={NavLink} {...props} />;
});

export function getHREFFromAbsoluteURL(url: string): string {
  if (url.startsWith(`http`)) {
    return url;
  }
  return `https://${url}`;
}
