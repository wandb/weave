/**
 * Display an info message to the user.
 */

import React from 'react';

import * as S from './Alert.styles';
import {IconName} from './Icon';

export const AlertSeverities = {
  Error: 'error',
  Warning: 'warning',
  Info: 'info',
  Success: 'success',
} as const;
export type AlertSeverity =
  (typeof AlertSeverities)[keyof typeof AlertSeverities];

const ICONS: Record<AlertSeverity, string> = {
  error: 'failed',
  warning: 'warning',
  info: 'info',
  success: 'checkmark-circle',
};

type AlertProps = {
  severity?: AlertSeverity;
  icon?: IconName | null;
  children: React.ReactNode;
  style?: React.CSSProperties;
};

export const Alert = ({severity, icon, children, style}: AlertProps) => {
  // User can override icon including to force it not to be shown.
  // Otherwise fallback to show the icon associated with the severity.
  const iconName =
    icon === null || icon ? icon : severity ? ICONS[severity] : null;
  return (
    <S.Alert severity={severity ?? 'default'} style={style}>
      {iconName !== null && <S.Icon name={iconName} width={16} height={16} />}
      <S.Message>{children}</S.Message>
    </S.Alert>
  );
};
