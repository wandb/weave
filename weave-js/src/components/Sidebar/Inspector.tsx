import React from 'react';
import styled from 'styled-components';

type InspectorProps = {
  className?: string;
  collapsed: boolean;
};

export const Inspector: React.FC<InspectorProps> = props => {
  const {collapsed, children} = props;
  return (
    <>
      <Wrapper
        data-test="weave-sidebar"
        className={props.className}
        collapsed={collapsed}>
        <Main>{children}</Main>
      </Wrapper>
    </>
  );
};

export default Inspector;

export const Wrapper = styled.div<{collapsed: boolean}>`
  height: 100vh;
  width: ${props => (props.collapsed ? 0 : 328)}px;
  background: white;
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  font-size: 15px;
  flex-direction: column;
`;

export const Main = styled.div`
  flex-grow: 1;
  overflow: hidden;
`;
