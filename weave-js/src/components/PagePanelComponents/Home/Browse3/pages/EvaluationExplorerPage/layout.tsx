import {Box} from '@mui/material';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import React from 'react';

import {BORDER_COLOR, HEADER_HEIGHT_PX} from './constants';

export const ConfigSection: React.FC<{
  title: string;
  icon: IconName;
  style?: React.CSSProperties;
  children?: React.ReactNode;
  error?: string;
  warning?: string;
  info?: string;
  headerAction?: React.ReactNode;
}> = ({title, icon, style, children, error, warning, info, headerAction}) => {
  return (
    <Column style={{flex: 0, ...style}}>
      <Row
        style={{
          alignItems: 'center',
          flex: 0,
          fontWeight: 600,
          paddingBottom: '8px',
          justifyContent: 'space-between',
        }}>
        <Row style={{alignItems: 'center', gap: '4px'}}>
          <Icon name={icon} />
          <span style={{marginLeft: '4px'}}>{title}</span>
        </Row>
        {headerAction && <div style={{marginLeft: 'auto'}}>{headerAction}</div>}
      </Row>
      {/* Validation messages */}
      {(error || warning || info) && (
        <div style={{marginBottom: '8px'}}>
          {error && (
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '4px',
                fontSize: '12px',
                color: '#ef4444',
                marginBottom: '4px',
              }}>
              <Icon name="failed" size="small" />
              <span>{error}</span>
            </div>
          )}
          {!error && warning && (
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '4px',
                fontSize: '12px',
                color: '#f59e0b',
                marginBottom: '4px',
              }}>
              <Icon name="warning" size="small" />
              <span>{warning}</span>
            </div>
          )}
          {!error && !warning && info && (
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '4px',
                fontSize: '12px',
                color: '#6b7280',
              }}>
              <Icon name="info" size="small" />
              <span>{info}</span>
            </div>
          )}
        </div>
      )}
      {children}
    </Column>
  );
};

export const Header: React.FC<{children?: React.ReactNode}> = ({children}) => {
  return (
    <div
      style={{
        height: HEADER_HEIGHT_PX,
        borderBottom: `1px solid ${BORDER_COLOR}`,
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        fontWeight: 600,
        fontSize: '18px',
        justifyContent: 'space-between',
        flex: `0 0 ${HEADER_HEIGHT_PX}px`,
      }}>
      {children}
    </div>
  );
};

export const Footer: React.FC<{children?: React.ReactNode}> = ({children}) => {
  return (
    <div
      style={{
        height: HEADER_HEIGHT_PX,
        borderTop: `1px solid ${BORDER_COLOR}`,
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        fontWeight: 600,
        fontSize: '18px',
        justifyContent: 'flex-end',
      }}>
      {children}
    </div>
  );
};

export const Row: React.FC<{
  style?: React.CSSProperties;
  children?: React.ReactNode;
}> = ({style, children}) => {
  return (
    <Box
      style={{
        display: 'flex',
        flexDirection: 'row',
        height: '100%',
        width: '100%',
        flex: 1,
        ...style,
      }}>
      {children}
    </Box>
  );
};

export const Column: React.FC<{
  style?: React.CSSProperties;
  children?: React.ReactNode;
}> = ({style, children}) => {
  return (
    <Box
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        flex: 1,
        ...style,
      }}>
      {children}
    </Box>
  );
};
