import React from 'react';

import styled from 'styled-components';
import * as LayoutElements from './LayoutElements';
import {Link} from 'react-router-dom';
import {MOON_800} from '@wandb/weave/common/css/color.styles';

const LeftNavItemBlock = styled(LayoutElements.HBlock)`
  margin: 0px 0px 0px 12px;
  padding: 0px 0px 0px 12px;
  border-radius: 4px;
  height: 36px;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  cursor: pointer;
  &:hover {
    background-color: #f5f6f7;
  }
`;

export const LeftNav: React.FC<{
  sections: LeftNavSectionProps[];
}> = props => {
  return (
    <LayoutElements.VBlock
      style={{
        width: '300px',
        paddingTop: '0px', // Cecile's design has spacing here, but i kind of like it without
        overflowY: 'auto',
      }}>
      {props.sections.map((section, i) => (
        <LeftNavSection key={i} {...section} />
      ))}
    </LayoutElements.VBlock>
  );
};

type LeftNavSectionProps = {
  title: string;
  items: LeftNavItemProps[];
};

const LeftNavSection: React.FC<LeftNavSectionProps> = props => {
  return (
    <LayoutElements.VBlock
      style={{
        marginBottom: '16px',
      }}>
      {/* Header */}
      <LayoutElements.HBlock
        style={{
          textTransform: 'uppercase',
          padding: '10px 24px',
          fontSize: '14px',
          position: 'sticky',
          backgroundColor: '#fff',
          top: 0,
        }}>
        {props.title}
      </LayoutElements.HBlock>
      {/* Items */}
      <LayoutElements.VBlock>
        {props.items.map((item, i) => (
          <LeftNavItem key={i} {...item} />
        ))}
      </LayoutElements.VBlock>
    </LayoutElements.VBlock>
  );
};

type LeftNavItemProps = {
  icon: React.FC;
  label: string;
  active?: boolean;
  to: string;
  onClick?: () => void;
};
const LeftNavItem: React.FC<LeftNavItemProps> = props => {
  return (
    <Link to={props.to} onClick={props.onClick}>
      <LeftNavItemBlock
        style={{
          backgroundColor: props.active ? '#A9EDF252' : '',
          color: props.active ? '#038194' : MOON_800,
          fontWeight: props.active ? 600 : '',
        }}>
        <props.icon />
        {props.label}
      </LeftNavItemBlock>
    </Link>
  );
};
