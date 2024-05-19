import {constStringList, Node} from '@wandb/weave/core';
import React, {useMemo, useState} from 'react';
import styled, {css} from 'styled-components';

import {GRAY_350, GRAY_500, TEAL} from '../../common/css/globals.styles';
import * as CGReact from '../../react';

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
Container.displayName = 'S.Container';

const Content = styled.div`
  flex: 1 1 auto;
  overflow: hidden;
`;
Content.displayName = 'S.Content';

const TabsContainer = styled.div`
  position: relative;
  display: flex;
  width: 100%;
  overflow-x: auto;
  flex: 0 0 auto;
  margin-bottom: 12px;

  &:after {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 1px;
    background-color: ${GRAY_350};
  }
`;
TabsContainer.displayName = 'S.TabsContainer';

const Tab = styled.div<{active: boolean}>`
  position: relative;
  z-index: 1;
  flex-shrink: 0;
  min-width: 50px;
  max-width: 100px;
  line-height: 32px;
  padding-bottom: 6px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  font-weight: 600;

  &:not(:first-child) {
    margin-left: 32px;
  }

  ${p =>
    !p.active
      ? css`
          &:not(:hover) {
            color: ${GRAY_500};
          }
        `
      : css`
          &:after {
            content: '';
            position: absolute;
            left: 0;
            right: 0;
            bottom: 0;
            height: 2px;
            background-color: ${TEAL};
          }
        `}
`;
Tab.displayName = 'S.Tab';
