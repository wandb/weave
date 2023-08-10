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
import {IconCategoryMultimodal} from '../../Icon';
import {
  useBoardGeneratorsForNode,
  useMakeLocalBoardFromNode,
} from '../../Panel2/pyBoardGen';
import {WeaveAnimatedLoader} from '../../Panel2/WeaveAnimatedLoader';
import {useNodeWithServerType} from '@wandb/weave/react';
import {MOON_250} from '@wandb/weave/common/css/color.styles';
import {useHistory} from 'react-router-dom';

const CenterSpace = styled(LayoutElements.VSpace)`
  border: 1px solid ${MOON_250};
  box-shadow: 0px 8px 16px 0px #0e10140a;
  border-top-left-radius: 12px;
`;
CenterSpace.displayName = 'S.CenterSpace';

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
CenterTableActionCellIcon.displayName = 'S.CenterTableActionCellIcon';

const DashboardTemplateItem = styled(LayoutElements.HStack)`
  padding: 8px 12px;
  border: 1px solid ${MOON_250};
  border-radius: 4px;
  cursor: pointer;
  &:hover {
    border: 1px solid #a9edf2;
    background-color: #a9edf212;
    color: #038194;
  }
`;
DashboardTemplateItem.displayName = 'S.DashboardTemplateItem';

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
  const history = useHistory();
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
              history.push('.');
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
            borderTop: `1px solid ${MOON_250}`,
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
  navigateToExpression: NavigateToExpressionType;
}> = ({expr, navigateToExpression}) => {
  const weave = useWeaveContext();
  const inputExpr = weave.expToString(expr);
  const refinedExpression = useNodeWithServerType(expr);
  const generators = useBoardGeneratorsForNode(expr);
  const [isGenerating, setIsGenerating] = React.useState(false);
  const makeBoardFromNode = useMakeLocalBoardFromNode();
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
      {generators.loading || refinedExpression.loading || isGenerating ? (
        <LayoutElements.VStack
          style={{
            alignItems: 'center',
            justifyContent: 'center',
            gap: '16px',
            color: '#8e949e',
          }}>
          <WeaveAnimatedLoader style={{height: '64px', width: '64px'}} />
        </LayoutElements.VStack>
      ) : (
        generators.result.length > 0 && (
          <LayoutElements.VBlock style={{gap: '8px'}}>
            <span style={{color: '#2B3038', fontWeight: 600}}>
              Available Templates
            </span>
            <LayoutElements.VStack
              style={{
                gap: '8px',
              }}>
              {generators.result.map(template => (
                <DashboardTemplate
                  key={template.op_name}
                  title={template.display_name}
                  subtitle={template.description}
                  onClick={() => {
                    setIsGenerating(true);
                    makeBoardFromNode(
                      template.op_name,
                      refinedExpression.result as any,
                      newDashExpr => {
                        navigateToExpression(newDashExpr);
                        setIsGenerating(false);
                      }
                    );
                  }}
                />
              ))}
            </LayoutElements.VStack>
          </LayoutElements.VBlock>
        )
      )}
    </LayoutElements.VStack>
  );
};

const DashboardTemplate: React.FC<{
  title: string;
  onClick: () => void;
  subtitle?: string;
}> = props => {
  return (
    <DashboardTemplateItem onClick={props.onClick}>
      <LayoutElements.VStack
        style={{
          overflow: 'hidden',
        }}>
        <LayoutElements.Block
          style={{
            fontWeight: 600,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}>
          {props.title}
        </LayoutElements.Block>
        <LayoutElements.Block
          style={{
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}>
          {props.subtitle}
        </LayoutElements.Block>
      </LayoutElements.VStack>
      <LayoutElements.VBlock
        style={{
          justifyContent: 'space-evenly',
        }}>
        <IconCategoryMultimodal
          style={{
            height: '60%',
            width: '100%',
          }}
        />
      </LayoutElements.VBlock>
    </DashboardTemplateItem>
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
      <HomeExpressionPreviewParts
        expr={expr}
        navigateToExpression={navigateToExpression}
      />
    </HomePreviewSidebarTemplate>
  );
};
