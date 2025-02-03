import copyToClipboard from 'copy-to-clipboard';
import _ from 'lodash';
import React, {
  forwardRef,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import styled from 'styled-components';

import {toast} from '../common/components/elements/Toast';
import {hexToRGB, MOON_300, MOON_600} from '../common/css/globals.styles';
import {useViewerInfo} from '../common/hooks/useViewerInfo';
import {getCookieBool, getFirebaseCookie} from '../common/util/cookie';
import {Button} from './Button';
import {Icon} from './Icon';
import {Tooltip} from './Tooltip';

const DEFAULT_TITLE = 'Something went wrong.';
const DEFAULT_SUBTITLE = 'An unexpected error occurred.';
const DEFAULT_SUBTITLE2 =
  'This error has been logged. Thank you for your patience.';

type ErrorPanelProps = {
  title?: string;
  subtitle?: string;
  subtitle2?: string;

  // These props are for error details object
  uuid?: string;
  timestamp?: Date;
  error?: Error;
};

export const Centered = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
`;
Centered.displayName = 'S.Centered';

export const Circle = styled.div<{$size: number; $hoverHighlight: boolean}>`
  border-radius: 50%;
  width: ${props => props.$size}px;
  height: ${props => props.$size}px;
  background-color: ${hexToRGB(MOON_300, 0.48)};
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  &:hover {
    background-color: ${props =>
      props.$hoverHighlight ? hexToRGB(MOON_300, 0.64) : undefined};
  }
`;
Circle.displayName = 'Circle';

export const Large = styled.div`
  width: fit-content;
  text-align: center;
  margin: 0 auto;
`;
Large.displayName = 'Large';

export const Title = styled.div`
  color: ${MOON_600};
  font-size: 18px;
  font-weight: 600;
  line-height: 140%;
  margin: 16px 0 8px 0;
`;
Title.displayName = 'Title';

export const Subtitle = styled.div`
  color: ${MOON_600};
  font-size: 15px;
  line-height: 140%;
`;
Subtitle.displayName = 'Subtitle';

export const ErrorPanelSmall = ({
  title,
  subtitle,
  subtitle2,
}: ErrorPanelProps) => {
  const titleStr = title ?? DEFAULT_TITLE;
  const subtitleStr = subtitle ?? DEFAULT_SUBTITLE;
  const subtitle2Str = subtitle2 ?? DEFAULT_SUBTITLE2;
  return (
    <Tooltip
      trigger={
        <Circle $size={22} $hoverHighlight={true}>
          <Icon name="warning" width={16} height={16} />
        </Circle>
      }>
      <b>{titleStr}</b> {subtitleStr} {subtitle2Str}
    </Tooltip>
  );
};

const getDateObject = (timestamp?: Date): Record<string, any> | null => {
  if (!timestamp) {
    return null;
  }
  return {
    // e.g. "2024-12-12T06:10:19.475Z",
    iso: timestamp.toISOString(),
    // e.g. "Thursday, December 12, 2024 at 6:10:19 AM Coordinated Universal Time"
    long: timestamp.toLocaleString('en-US', {
      weekday: 'long',
      year: 'numeric', // Full year
      month: 'long', // Full month name
      day: 'numeric', // Day of the month
      hour: 'numeric', // Hour (12-hour or 24-hour depending on locale)
      minute: 'numeric',
      second: 'numeric',
      timeZone: 'UTC', // Ensures it's in UTC
      timeZoneName: 'long', // Full time zone name
    }),
    user: timestamp.toLocaleString('en-US', {
      dateStyle: 'full',
      timeStyle: 'full',
    }),
  };
};

const getErrorObject = (error?: Error): Record<string, any> | null => {
  if (!error) {
    return null;
  }

  // Error object properties are not enumerable so we have to copy them manually
  const stack = (error.stack ?? '').split('\n');
  return {
    message: error.message,
    stack,
  };
};

export const ErrorPanelLarge = forwardRef<HTMLDivElement, ErrorPanelProps>(
  ({title, subtitle, subtitle2, uuid, timestamp, error}, ref) => {
    const titleStr = title ?? DEFAULT_TITLE;
    const subtitleStr = subtitle ?? DEFAULT_SUBTITLE;
    const subtitle2Str = subtitle2 ?? DEFAULT_SUBTITLE2;

    const {userInfo} = useViewerInfo();

    const onClick = useCallback(() => {
      const betaVersion = getFirebaseCookie('betaVersion');
      const isUsingAdminPrivileges = getCookieBool('use_admin_privileges');
      const {location, navigator, screen} = window;
      const {userAgent, language} = navigator;
      const details = {
        uuid,
        url: location.href,
        error: getErrorObject(error),
        timestamp_err: getDateObject(timestamp),
        timestamp_copied: getDateObject(new Date()),
        user: _.pick(userInfo, ['id', 'username']), // Skipping teams and admin
        cookies: {
          ...(betaVersion && {betaVersion}),
          ...(isUsingAdminPrivileges && {use_admin_privileges: true}),
        },
        browser: {
          userAgent,
          language,
          screenSize: {
            width: screen.width,
            height: screen.height,
          },
          viewportSize: {
            width: window.innerWidth,
            height: window.innerHeight,
          },
        },
      };
      const detailsText = JSON.stringify(details, null, 2);
      copyToClipboard(detailsText);
      toast('Copied to clipboard');
    }, [uuid, timestamp, error, userInfo]);

    return (
      <Large ref={ref}>
        <Circle $size={40} $hoverHighlight={false}>
          <Icon name="warning" width={24} height={24} />
        </Circle>
        <Title>{titleStr}</Title>
        <Subtitle>{subtitleStr}</Subtitle>
        <Subtitle>{subtitle2Str}</Subtitle>
        <Button
          style={{marginTop: 16}}
          size="small"
          variant="secondary"
          icon="copy"
          onClick={onClick}>
          Copy error details
        </Button>
      </Large>
    );
  }
);

export const ErrorPanel = (props: ErrorPanelProps) => {
  const thisRef = useRef<HTMLDivElement | null>(null);
  const largeRef = useRef<HTMLDivElement | null>(null);
  const [mode, setMode] = useState('measure');

  useEffect(() => {
    const thisW = thisRef.current?.clientWidth ?? 0;
    const thisH = thisRef.current?.clientHeight ?? 0;
    const largeW = largeRef.current?.clientWidth ?? 0;
    const largeH = largeRef.current?.clientHeight ?? 0;
    const largeFits = thisW >= largeW && thisH >= largeH;
    setMode(largeFits ? 'large' : 'small');
  }, []);

  return (
    <div ref={thisRef} style={{height: '100%'}}>
      {mode === 'large' ? (
        <Centered>
          <ErrorPanelLarge {...props} ref={largeRef} />
        </Centered>
      ) : mode === 'small' ? (
        <Centered>
          <ErrorPanelSmall {...props} />
        </Centered>
      ) : (
        <div style={{visibility: 'hidden'}}>
          <ErrorPanelLarge {...props} ref={largeRef} />
        </div>
      )}
    </div>
  );
};
