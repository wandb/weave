import React from 'react';
import * as LayoutElements from './LayoutElements';
import styled from 'styled-components';
import {IconClose, IconOpenNewTab} from '../../Panel2/Icons';
import {NavigateToExpressionType, SetPreviewNodeType} from './common';
import {WBButton} from '@wandb/weave/common/components/elements/WBButtonNew';
import {Node} from '@wandb/weave/core';
import {WeaveExpression} from '@wandb/weave/panel/WeaveExpression';
import {PreviewNode} from './PreviewNode';
import {useWeaveContext} from '@wandb/weave/context';

const CenterSpace = styled(LayoutElements.VSpace)`
  border: 1px solid #dadee3;
  box-shadow: 0px 8px 16px 0px #0e10140a;
  border-top-left-radius: 12px;
`;

const CenterTableActionCellIcon = styled(LayoutElements.VStack)`
  align-items: center;
  justify-content: center;
  height: 32px;
  width: 32px;
  border-radius: 4px;
  &:hover {
    background-color: #a9edf252;
    color: #038194;
  }
`;

export const HomePreviewSidebarTemplate: React.FC<{
  title: string;
  setPreviewNode: SetPreviewNodeType;
  children?: React.ReactNode;
  primaryAction?: {
    icon: React.FC;
    label: string;
    onClick: () => void;
  };
  secondaryAction?: {
    icon: React.FC;
    label: string;
    onClick: () => void;
  };
}> = props => {
  return (
    <CenterSpace>
      <LayoutElements.HBlock
        style={{
          height: '70px',
          alignContent: 'center',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '12px',
          padding: '0px 24px',
        }}>
        <LayoutElements.VSpace
          style={{justifyContent: 'center', fontSize: '20px', fontWeight: 600}}>
          {props.title}
        </LayoutElements.VSpace>
        {/* <LayoutElements.Block>
          <IconOverflowHorizontal />
        </LayoutElements.Block> */}
        <CenterTableActionCellIcon>
          <IconClose
            style={{
              cursor: 'pointer',
            }}
            onClick={e => {
              e.stopPropagation();
              props.setPreviewNode(undefined);
            }}
          />
        </CenterTableActionCellIcon>
      </LayoutElements.HBlock>
      <LayoutElements.VSpace
        style={{
          overflow: 'auto',
          padding: '0px 24px',
        }}>
        {props.children}
      </LayoutElements.VSpace>
      {(props.primaryAction || props.secondaryAction) && (
        <LayoutElements.HBlock
          style={{
            // height: '72px',
            borderTop: '1px solid #dadee3',
            padding: '12px',
            gap: '12px',
          }}>
          {props.primaryAction && (
            <WBButton
              variant={`confirm`}
              onClick={props.primaryAction.onClick}
              fluid>
              <LayoutElements.HStack
                style={{
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}>
                <props.primaryAction.icon />
                {props.primaryAction.label}
              </LayoutElements.HStack>
            </WBButton>
          )}
          {props.secondaryAction && (
            <WBButton onClick={props.secondaryAction.onClick} fluid>
              <LayoutElements.HStack
                style={{
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}>
                <props.secondaryAction.icon />
                {props.secondaryAction.label}
              </LayoutElements.HStack>
            </WBButton>
          )}
        </LayoutElements.HBlock>
      )}
    </CenterSpace>
  );
};

export const HomeExpressionPreviewParts: React.FC<{
  expr: Node;
}> = ({expr}) => {
  const weave = useWeaveContext();
  const inputExpr = weave.expToString(expr);
  return (
    <LayoutElements.VStack style={{gap: '16px'}}>
      <LayoutElements.VBlock style={{gap: '8px'}}>
        <span style={{color: '#2B3038', fontWeight: 600}}>Preview</span>
        <LayoutElements.Block>
          <PreviewNode inputExpr={inputExpr} />
        </LayoutElements.Block>
      </LayoutElements.VBlock>
      <LayoutElements.VBlock style={{gap: '8px'}}>
        <span style={{color: '#2B3038', fontWeight: 600}}>Expression</span>
        <LayoutElements.Block>
          {/* <Unclickable style={{}}> */}
          <WeaveExpression
            expr={expr}
            onMount={() => {}}
            onFocus={() => {}}
            onBlur={() => {}}
            frozen
          />
          {/* </Unclickable> */}
        </LayoutElements.Block>
      </LayoutElements.VBlock>
    </LayoutElements.VStack>
  );
};

export const HomeBoardPreview: React.FC<{
  expr: Node;
  name: string;
  setPreviewNode: SetPreviewNodeType;
  navigateToExpression: NavigateToExpressionType;
}> = ({expr, name, setPreviewNode, navigateToExpression}) => {
  return (
    <HomePreviewSidebarTemplate
      title={name}
      setPreviewNode={setPreviewNode}
      primaryAction={{
        icon: IconOpenNewTab,
        label: `Open board`,
        onClick: () => {
          navigateToExpression(expr);
        },
      }}>
      <HomeExpressionPreviewParts expr={expr} />
    </HomePreviewSidebarTemplate>
  );
};
