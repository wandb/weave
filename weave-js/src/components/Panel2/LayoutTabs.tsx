import {constStringList, Node} from '@wandb/weave/core';
import React, {useMemo, useState} from 'react';

import * as CGReact from '../../react';
import styled, {css} from 'styled-components';
import {GRAY_350, TEAL} from '../../common/css/globals.styles';

const HOVER_COLOR = '#00879d';
const ACTIVE_COLOR = '#6ba6fa';

export const Tabs: React.FC<{
  input: Node;
  activeIndex: number;
  setActiveIndex: (newActiveIndex: number) => void;
}> = props => {
  const {input, activeIndex, setActiveIndex} = props;
  const tabNamesQuery = CGReact.useNodeValue(input);
  const tabNames = useMemo(() => {
    return tabNamesQuery.result ?? ['loading...'];
  }, [tabNamesQuery.result]);

  return (
    <TabsContainer>
      {tabNames.map((name: string, i: number) => (
        <Tab
          key={i}
          active={activeIndex === i}
          onClick={() => setActiveIndex(i)}>
          {name}
        </Tab>
      ))}
    </TabsContainer>
  );
};

export const LayoutTabs: React.FC<{
  tabNames: string[];
  renderPanel: (panel: {id: string}) => React.ReactNode;
}> = props => {
  const [activeIndex, setActiveIndex] = useState(0);
  return (
    <Container>
      <Tabs
        input={constStringList(props.tabNames)}
        activeIndex={activeIndex}
        setActiveIndex={setActiveIndex}
      />
      <Content>{props.renderPanel({id: props.tabNames[activeIndex]})}</Content>
    </Container>
  );
};

const Container = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
`;

const Content = styled.div`
  flex: 1 1 auto;
  overflow: hidden;
`;

const TabsContainer = styled.div`
  display: flex;
  width: 100%;
  overflow-x: auto;
  flex: 0 0 auto;
  border-bottom: 1px solid ${GRAY_350};
`;

const Tab = styled.div<{active: boolean}>`
  position: relative;
  flex-shrink: 0;
  min-width: 50px;
  max-width: 100px;
  line-height: 32px;
  display: flex;
  justify-content: center;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;

  &:not(:first-child) {
    margin-left: 32px;
  }

  ${p =>
    !p.active
      ? css`
          &:hover {
            color: ${HOVER_COLOR};
          }
          &:after {
            content: '';
            position: absolute;
            left: 0;
            right: 0;
            bottom: 0;
            height: 2px;
            background-color: ${TEAL};
          }
        `
      : css`
          color: ${ACTIVE_COLOR};
        `}
`;
