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

export const getIsExternalLink = (url: string) => {
  return (
    url.startsWith('http') || url.startsWith('//') || url.indexOf('://') > 0
  );
};

export const getIsMailToLink = (url?: string) => {
  return url != null && url.startsWith('mailto:');
};

export const getAbsolutePrefixedUrl = (href?: string) => {
  if (href == null) {
    return undefined;
  }

  if (getIsExternalLink(href)) {
    return getConfig().urlPrefixed(href);
  }

  return href;
};

export const MailTo: FCWithRef<
  React.AnchorHTMLAttributes<HTMLAnchorElement>,
  HTMLAnchorElement
> = React.memo(
  React.forwardRef(({children, href, ...passthroughProps}, ref) => {
    if (!getIsMailToLink(href)) {
      throw new Error('use TargetBlank or Link component instead');
    }

    return (
      // eslint-disable-next-line wandb/no-a-tags
      <A
        target="_blank"
        rel="noopener noreferrer"
        href={href}
        {...passthroughProps}
        ref={ref}>
        {children}
      </A>
    );
  })
);

/**
 * This will only allow safe external links that start with http.
 * This enforces absolute prefixed url for blank targets.
 */
export const SanitizedTargetBlank: FCWithRef<
  React.AnchorHTMLAttributes<HTMLAnchorElement>,
  HTMLAnchorElement
> = React.memo(
  React.forwardRef(({children, href, ...passthroughProps}, ref) => {
    if (getIsMailToLink(href)) {
      throw new Error('use MailTo component instead');
    }
    if (href != null && !getIsExternalLink(href)) {
      throw new Error('use a Link component from react-router-dom instead');
    }

    return (
      // eslint-disable-next-line wandb/no-a-tags
      <A
        target="_blank"
        rel="noopener noreferrer"
        href={getAbsolutePrefixedUrl(href)}
        {...passthroughProps}
        ref={ref}>
        {children}
      </A>
    );
  })
);

/**
 * Warning: do not pass in untrusted hrefs!
 */
export const TargetBlank: FCWithRef<
  React.AnchorHTMLAttributes<HTMLAnchorElement>,
  HTMLAnchorElement
> = React.memo(
  React.forwardRef(({children, href, ...passthroughProps}, ref) => {
    if (getIsMailToLink(href)) {
      throw new Error('use MailTo component instead');
    }

    if (href != null && getIsExternalLink(href)) {
    }

    // Enforce an absolute prefixed url for blank targets
    const parsedHref =
      href != null && getIsExternalLink(href)
        ? getAbsolutePrefixedUrl(href)
        : href;

    return (
      // eslint-disable-next-line wandb/no-a-tags
      <A
        target="_blank"
        rel="noopener noreferrer"
        href={parsedHref}
        {...passthroughProps}
        ref={ref}>
        {children}
      </A>
    );
  })
);

export type LinkProps = RRLinkProps & {
  ReactRouterLinkComp?: React.FC<any>;
  newTab?: boolean;
};

export const Link: FCWithRef<LinkProps, HTMLAnchorElement> = React.memo(
  React.forwardRef(
    (
      {ReactRouterLinkComp = RRLink, newTab = true, children, ...passProps},
      ref
    ) => {
      const {to} = passProps;
      const isExternalLink = typeof to === 'string' && getIsExternalLink(to);

      if (isExternalLink) {
        const safeUrl = getSafeUrlWithoutXss(to);
        if (newTab) {
          return (
            <SanitizedTargetBlank {...passProps} href={safeUrl} ref={ref}>
              {children}
            </SanitizedTargetBlank>
          );
        }

        return (
          // eslint-disable-next-line wandb/no-a-tags
          <a {...passProps} href={safeUrl} ref={ref}>
            {children}
          </a>
        );
      }

      return (
        <ReactRouterLinkComp {...passProps} ref={ref}>
          {children}
        </ReactRouterLinkComp>
      );
    }
  )
);

type NavLinkProps = Omit<RRNavLinkProps, 'className' | 'style'> & {
  className?: string;
  style?: CSSProperties;
};

export const NavLink: React.FC<NavLinkProps> = React.memo(props => {
  return <Link ReactRouterLinkComp={RRNavLink} {...props} />;
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

/**
 * SECURITY CHECK: validate that this URL is actually a link to a webpage - if not, omit it.
 * Rendering non- http/https links is a risk for XSS, even when they use target="_blank"
 * because users can still choose to right click and open in the same tab */
export const getSafeUrlWithoutXss = (url: string): string => {
  try {
    const urlForChecking = new URL(url);
    if (
      urlForChecking.protocol !== 'http:' &&
      urlForChecking.protocol !== 'https:'
    ) {
      console.error('Unsafe URL was attempted to be rendered: ' + url);
      // for now, just blanking out the URL to prevent the unsafe link from getting rendered,
      // not trying to make this a good experience, since users are very unlikely to see this
      return '';
    }
    return url;
  } catch (e) {
    // URL constructor throws on invalid URLs - in that case, we don't want to allow that as a link
    return '';
  }
};
