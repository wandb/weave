import {MOON_250} from '@wandb/weave/common/css/color.styles';
import React from 'react';
import styled from 'styled-components';

type PanelInteractDrawerProps = {
  active: boolean;
  sticky?: boolean;
};

export const PanelInteractDrawer: React.FC<PanelInteractDrawerProps> = ({
  active,
  children,
  sticky = false,
}) => {
  return (
    <Container active={active} sticky={sticky} data-test="weave-sidebar">
      <Content>{children}</Content>
    </Container>
  );
};

export default PanelInteractDrawer;

const WIDTH_PX = 328;

export const Container = styled.div<{active: boolean; sticky: boolean}>`
  background: white;
  z-index: 10;
  flex-shrink: 0;
  font-size: 15px;
  overflow: hidden;
  border-left: ${p => (p.active ? `1px solid ${MOON_250}` : 'none')};
  // Alternative to the border:
  /* 
  z-index: 1;
  box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.2); 
  */
  width: ${p => (p.active ? WIDTH_PX : 0)}px;
  // Don't do this, it makes open and closing the drawer janky
  // transition: width 0.3s;
  height: ${p => (p.sticky ? '100vh' : undefined)};
  position: ${p => (p.sticky ? 'sticky' : undefined)};
  top: ${p => (p.sticky ? 0 : undefined)};
`;

export const Content = styled.div`
  width: ${WIDTH_PX}px;
  height: 100%;
`;
