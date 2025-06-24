import {Box} from '@mui/material';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import React from 'react';

import {BORDER_COLOR, HEADER_HEIGHT_PX} from './constants';

export const ConfigSection: React.FC<{
  title: string;
  icon: IconName;
  style?: React.CSSProperties;
  children?: React.ReactNode;
}> = ({title, icon, style, children}) => {
  return (
    <Column style={{padding: '8px 16px 16px 16px', flex: 0, ...style}}>
      <Row
        style={{
          alignItems: 'center',
          flex: 0,
          fontWeight: 600,
          paddingBottom: '8px',
        }}>
        <Icon name={icon} />
        <span style={{marginLeft: '4px'}}>{title}</span>
      </Row>
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
