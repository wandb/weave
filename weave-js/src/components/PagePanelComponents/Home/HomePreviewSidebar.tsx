import {WBButton} from '@wandb/weave/common/components/elements/WBButtonNew';
import {
  MOON_250,
  MOON_500,
  MOON_800,
  TEAL_400,
} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import * as Tabs from '@wandb/weave/components/Tabs';
import {Pill} from '@wandb/weave/components/Tag';
import {useWeaveContext} from '@wandb/weave/context';
import {Node, NodeOrVoidNode} from '@wandb/weave/core';
import {WeaveExpression} from '@wandb/weave/panel/WeaveExpression';
import {useNodeWithServerType} from '@wandb/weave/react';
import {trackNewBoardFromTemplateClicked} from '@wandb/weave/util/events';
import React, {useEffect, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {maybePluralize} from '../../../core/util/string';
import {ErrorBoundary} from '../../ErrorBoundary';
import {IconClose, IconOpenNewTab} from '../../Panel2/Icons';
import {useArtifactDependencyOfForNode} from '../../Panel2/pyArtifactDep';
import {
  useBoardGeneratorsForNode,
  useMakeLocalBoardFromNode,
} from '../../Panel2/pyBoardGen';
import {WeaveAnimatedLoader} from '../../Panel2/WeaveAnimatedLoader';
import {BoardsTab} from './BoardsTab';
import {
  getArtifactVersionNodeFromUri,
  NavigateToExpressionType,
  SetPreviewNodeType,
} from './common';
import {
  ActionCell,
  CenterBrowserActionType,
  CenterBrowserDataType,
} from './HomeCenterBrowser';
import * as LayoutElements from './LayoutElements';
import {Unclickable} from './PreviewNode';
import * as S from './styles';

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

const DashboardTemplateItem = styled(LayoutElements.VBlock)`
  padding: 16px 16px 16px 12px;
  border: 1px solid ${MOON_250};
  border-radius: 4px;
  cursor: pointer;
  &:hover {
    border: 1px solid ${TEAL_400};
  }
`;
DashboardTemplateItem.displayName = 'S.DashboardTemplateItem';

const DashboardTemplateItemText = styled(LayoutElements.Block)`
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
`;
DashboardTemplateItemText.displayName = 'S.DashboardTemplateItemText';

const TabContentWrapper = styled.div`
  overflow-y: scroll;
  padding: 16px;
  height: 100%;
`;
TabContentWrapper.displayName = 'S.TabContentWrapper';

const Label = styled.span`
  color: ${MOON_500};
  font-size: 15px;
  font-weight: 400;
  line-height: 21px;
`;
Label.displayName = 'S.Label';

const HomeExpressionPreviewPartsWrapper = styled.div`
  height: 100%;

  > .tw-style {
    height: 100%;
  }
`;
HomeExpressionPreviewPartsWrapper.displayName =
  'S.HomeExpressionPreviewPartsWrapper';

type HomePreviewSidebarTemplateProps<RT extends CenterBrowserDataType> = {
  title: string;
  row?: RT;
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
  actions?: Array<CenterBrowserActionType<RT>>;
  emptyData?: boolean;
  emptyDataMessage?: React.ReactNode;
};

export const HomePreviewSidebarTemplate = <RT extends CenterBrowserDataType>(
  props: HomePreviewSidebarTemplateProps<RT> & {
    // Temp hack until we decouple history from all these components
    isTemplate?: boolean;
  }
) => {
  const history = useHistory();
  return (
    <CenterSpace>
      <LayoutElements.HBlock
        style={{
          height: '70px',
          alignContent: 'center',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '8px',
          padding: '0px 16px',
        }}>
        <LayoutElements.VSpace
          style={{justifyContent: 'center', fontSize: '20px', fontWeight: 600}}>
          {props.title}
        </LayoutElements.VSpace>
        {/* <LayoutElements.Block>
          <IconOverflowHorizontal />
        </LayoutElements.Block> */}
        {props.row && props.actions && props.actions.length > 0 && (
          <CenterTableActionCellIcon>
            <ActionCell actions={props.actions} row={props.row} />
          </CenterTableActionCellIcon>
        )}
        <CenterTableActionCellIcon>
          <IconClose
            style={{
              cursor: 'pointer',
            }}
            onClick={e => {
              if (!props.isTemplate) {
                history.push('.');
              } else {
                props.setPreviewNode(undefined);
              }
            }}
          />
        </CenterTableActionCellIcon>
      </LayoutElements.HBlock>
      <LayoutElements.VSpace>
        {props.emptyData ? props.emptyDataMessage : props.children}
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

const Loader = () => (
  <LayoutElements.VStack
    style={{
      marginTop: '12px',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '16px',
      color: '#8e949e',
    }}>
    <WeaveAnimatedLoader style={{height: '64px', width: '64px'}} />
  </LayoutElements.VStack>
);

type Template = {
  display_name: string;
  description: string;
  op_name: string;
};

export const SEED_BOARD_OP_NAME = 'py_board-seed_board';
const OPEN_AI_OP_NAME = 'py_board-llm_completions_monitor';
const TRACE_OP_NAME = 'py_board-trace_monitor';
const RECOMMENDED_TEMPLATES = [OPEN_AI_OP_NAME, TRACE_OP_NAME];
const FALL_BACK_TEMPLATE = SEED_BOARD_OP_NAME;
// Returns a recommended template in order of recommendation if they exist
// else returns any template thats not the fallback as recommended
// else returns fallback
const getRecommendedTemplateInfo = (generators: Template[]) => {
  for (const templateOpName of RECOMMENDED_TEMPLATES) {
    const recommendedTemplate = generators.find(
      template => template.op_name === templateOpName
    );
    if (recommendedTemplate) {
      return recommendedTemplate;
    }
  }
  return (
    generators.find(template => template.op_name !== FALL_BACK_TEMPLATE) ||
    generators.find(template => template.op_name === FALL_BACK_TEMPLATE)
  );
};

export const HomeExpressionPreviewParts: React.FC<{
  expr: Node;
  navigateToExpression: NavigateToExpressionType;
  generatorAllowList?: string[];
}> = ({expr, navigateToExpression, generatorAllowList}) => {
  const refinedExpression = useNodeWithServerType(expr);
  const generators = useBoardGeneratorsForNode(expr);
  const [isGenerating, setIsGenerating] = useState(false);
  const [tabValue, setTabValue] = useState('Overview');

  const isLoadingTemplates =
    generators.loading || refinedExpression.loading || isGenerating;
  const finalGenerators = useMemo(() => {
    if (generators.loading || !generators.result) {
      return [];
    }

    if (!generatorAllowList) {
      return generators.result;
    }
    return generators.result.filter(generator =>
      generatorAllowList.includes(generator.op_name)
    );
  }, [generatorAllowList, generators.loading, generators.result]);
  const hasTemplates = !isLoadingTemplates && finalGenerators.length > 1;
  const recommendedTemplateInfo = getRecommendedTemplateInfo(finalGenerators);

  // Create an Artifact version node to look up the artifacts that depend on this one.
  // TODO: Implement a less brittle way of pulling the URI from the get op.
  //       This should also let us get rid of the "any".
  let nodeArtifactVersion = null;
  const outputNode = expr as any;
  const sourceType = outputNode.fromOp.name;
  if (sourceType === 'table-rows') {
    const uri =
      outputNode.fromOp.inputs.table.fromOp.inputs.file.fromOp.inputs
        .artifactVersion.fromOp.inputs.uri.val;
    nodeArtifactVersion = getArtifactVersionNodeFromUri(uri, 'run_table');
  } else if (sourceType === 'stream_table-rows') {
    const uri = outputNode.fromOp.inputs.self.fromOp.inputs.uri.val;
    nodeArtifactVersion = getArtifactVersionNodeFromUri(uri, 'stream_table');
  } else {
    // Previewing a board.
  }

  const hasBoardsTab = nodeArtifactVersion != null;
  const dependencyQuery = useArtifactDependencyOfForNode(nodeArtifactVersion);

  useEffect(() => {
    setTabValue('Overview');
  }, [expr]);

  return (
    <HomeExpressionPreviewPartsWrapper>
      <Tabs.Root
        value={tabValue}
        onValueChange={(val: string) => setTabValue(val)}
        className="h-full">
        <Tabs.List className="px-16">
          <Tabs.Trigger value="Overview">Overview</Tabs.Trigger>
          {hasTemplates && (
            <Tabs.Trigger value="Templates">Templates</Tabs.Trigger>
          )}
          {hasBoardsTab && <Tabs.Trigger value="Boards">Boards</Tabs.Trigger>}
        </Tabs.List>
        {/* 38 px is the height of the tab header, to make sure the height of content doesnt exceed window, its explicitly set here */}
        <Tabs.Content value="Overview" style={{height: 'calc( 100% - 38px )'}}>
          <TabContentWrapper>
            <OverviewTab
              expr={expr}
              navigateToExpression={navigateToExpression}
              refinedExpression={refinedExpression}
              recommendedTemplateInfo={recommendedTemplateInfo}
              isLoadingTemplates={isLoadingTemplates}
              setIsGenerating={setIsGenerating}
              generators={finalGenerators}
              setTabValue={setTabValue}
              hasTemplates={hasTemplates}
            />
          </TabContentWrapper>
        </Tabs.Content>
        {hasTemplates && (
          <Tabs.Content
            value="Templates"
            style={{height: 'calc( 100% - 38px )'}}>
            <TabContentWrapper>
              <TemplateTab
                navigateToExpression={navigateToExpression}
                refinedExpression={refinedExpression}
                recommendedTemplateInfo={recommendedTemplateInfo}
                isLoadingTemplates={isLoadingTemplates}
                setIsGenerating={setIsGenerating}
                generators={finalGenerators}
              />
            </TabContentWrapper>
          </Tabs.Content>
        )}
        <Tabs.Content value="Boards" style={{height: 'calc( 100% - 38px )'}}>
          {hasBoardsTab && (
            <BoardsTab
              dependencyQuery={dependencyQuery}
              navigateToExpression={navigateToExpression}
              isLoadingTemplates={isLoadingTemplates}
              setIsGenerating={setIsGenerating}
              setTabValue={setTabValue}
              hasTemplates={hasTemplates}
              refinedExpression={refinedExpression}
            />
          )}
        </Tabs.Content>
      </Tabs.Root>
    </HomeExpressionPreviewPartsWrapper>
  );
};

// It's possible for the artifact fetch to fail, and we don't want that to crash the whole page.
// For example, if the artifact version is deleted in the app UI but the sequence remains.
export const SafeHomeExpressionPreviewParts: React.FC<{
  expr: Node;
  navigateToExpression: NavigateToExpressionType;
  generatorAllowList?: string[];
}> = props => {
  return (
    <ErrorBoundary>
      <HomeExpressionPreviewParts {...props} />
    </ErrorBoundary>
  );
};

const OverviewTab = ({
  expr,
  navigateToExpression,
  refinedExpression,
  recommendedTemplateInfo,
  isLoadingTemplates,
  setIsGenerating,
  generators,
  setTabValue,
  hasTemplates,
}: {
  expr: Node;
  navigateToExpression: NavigateToExpressionType;
  refinedExpression: {
    loading: boolean;
    result: NodeOrVoidNode;
  };
  recommendedTemplateInfo?: Template;
  isLoadingTemplates: boolean;
  setIsGenerating: React.Dispatch<React.SetStateAction<boolean>>;
  generators: Template[];
  setTabValue: React.Dispatch<React.SetStateAction<string>>;
  hasTemplates: boolean;
}) => {
  const weave = useWeaveContext();
  const makeBoardFromNode = useMakeLocalBoardFromNode();
  const [copyButtonText, setCopyButtonText] = useState<'Copy' | 'Copied'>(
    'Copy'
  );
  const showSeedBoard = generators.find(g => g.op_name === SEED_BOARD_OP_NAME)
    ? true
    : false;

  return (
    <LayoutElements.VStack style={{gap: '16px'}}>
      {/*  Only show the create a board section if a board can be created ie there exists at least one template */}
      {isLoadingTemplates ? (
        <Loader />
      ) : (
        <>
          {generators.length > 0 && (
            <LayoutElements.VBlock style={{gap: '8px', paddingBottom: '32px'}}>
              <LayoutElements.BlockHeader>
                CREATE A BOARD
                {hasTemplates && (
                  <Button
                    onClick={() => {
                      setTabValue('Templates');
                    }}
                    size="small"
                    variant="ghost">
                    View all templates
                  </Button>
                )}
              </LayoutElements.BlockHeader>
              <LayoutElements.VStack
                style={{
                  gap: '8px',
                }}>
                {recommendedTemplateInfo &&
                  recommendedTemplateInfo.op_name !== SEED_BOARD_OP_NAME && (
                    <>
                      <DashboardTemplate
                        key={recommendedTemplateInfo.op_name}
                        title={recommendedTemplateInfo.display_name}
                        subtitle={recommendedTemplateInfo.description}
                        onButtonClick={() => {
                          setIsGenerating(true);
                          makeBoardFromNode(
                            recommendedTemplateInfo.op_name,
                            refinedExpression.result as any,
                            newDashExpr => {
                              setIsGenerating(false);
                              navigateToExpression(newDashExpr);
                            }
                          );
                          const templateName = processTemplateNameForTracking(
                            recommendedTemplateInfo.display_name
                          );
                          trackNewBoardFromTemplateClicked(
                            'table-overview-tab',
                            templateName
                          );
                        }}
                        isExpanded={true}
                        isRecommended={true}
                      />
                      {showSeedBoard && (
                        <Label
                          style={{display: 'flex', justifyContent: 'center'}}>
                          or
                        </Label>
                      )}
                    </>
                  )}
                {showSeedBoard && (
                  <DashboardTemplate
                    key={SEED_BOARD_OP_NAME}
                    subtitle="Seed a board with a simple visualization of this table."
                    onButtonClick={() => {
                      setIsGenerating(true);
                      makeBoardFromNode(
                        SEED_BOARD_OP_NAME,
                        refinedExpression.result as any,
                        newDashExpr => {
                          setIsGenerating(false);
                          navigateToExpression(newDashExpr);
                        }
                      );
                      trackNewBoardFromTemplateClicked(
                        'table-overview-tab',
                        'simple-table-visualization'
                      );
                    }}
                    isExpanded={true}
                    buttonVariant={
                      generators.length === 1 ? 'primary' : 'secondary'
                    }
                    buttonText="New board"
                  />
                )}
              </LayoutElements.VStack>
            </LayoutElements.VBlock>
          )}
          <LayoutElements.VBlock style={{gap: '8px'}}>
            <LayoutElements.BlockHeader>
              EXPRESSION
              <Button
                onClick={() => {
                  navigator.clipboard.writeText(weave.expToString(expr));
                  setCopyButtonText('Copied');
                  setTimeout(() => {
                    setCopyButtonText('Copy');
                  }, 3000);
                }}
                size="small"
                variant="ghost"
                icon="copy">
                {copyButtonText}
              </Button>
            </LayoutElements.BlockHeader>
            <LayoutElements.Block>
              <Unclickable>
                <WeaveExpression
                  expr={expr}
                  onMount={() => {}}
                  onFocus={() => {}}
                  onBlur={() => {}}
                  frozen
                />
              </Unclickable>
            </LayoutElements.Block>
          </LayoutElements.VBlock>
        </>
      )}
    </LayoutElements.VStack>
  );
};

const TemplateTab = ({
  navigateToExpression,
  refinedExpression,
  recommendedTemplateInfo,
  isLoadingTemplates,
  setIsGenerating,
  generators,
}: {
  navigateToExpression: NavigateToExpressionType;
  refinedExpression: {
    loading: boolean;
    result: NodeOrVoidNode;
  };
  recommendedTemplateInfo?: Template;
  isLoadingTemplates: boolean;
  setIsGenerating: React.Dispatch<React.SetStateAction<boolean>>;
  generators: Template[];
}) => {
  const makeBoardFromNode = useMakeLocalBoardFromNode();
  const [expandedTemplate, setExpandedTemplate] = useState<string | null>(
    recommendedTemplateInfo?.op_name || null
  );

  return isLoadingTemplates ? (
    <Loader />
  ) : (
    <LayoutElements.VStack
      style={{
        gap: '8px',
        paddingBottom: '32px',
      }}>
      <S.ObjectCount>
        {maybePluralize(generators.length, 'template', 's')}
      </S.ObjectCount>
      <Label
        style={{
          marginBottom: '8px',
        }}>
        Weave analyzes your data schema to suggest relevant board templates.
        Select a template to instantly generate a board.
      </Label>
      {recommendedTemplateInfo && (
        <DashboardTemplate
          key={recommendedTemplateInfo.op_name}
          title={recommendedTemplateInfo.display_name}
          subtitle={recommendedTemplateInfo.description}
          onButtonClick={() => {
            setIsGenerating(true);
            makeBoardFromNode(
              recommendedTemplateInfo.op_name,
              refinedExpression.result as any,
              newDashExpr => {
                setIsGenerating(false);
                navigateToExpression(newDashExpr);
              }
            );
            const templateName = processTemplateNameForTracking(
              recommendedTemplateInfo.display_name
            );
            trackNewBoardFromTemplateClicked(
              'table-template-tab',
              templateName
            );
          }}
          onClick={() => {
            setExpandedTemplate(recommendedTemplateInfo.op_name);
          }}
          isExpanded={recommendedTemplateInfo.op_name === expandedTemplate}
          isRecommended={true}
        />
      )}
      {generators.map(template => {
        if (
          recommendedTemplateInfo &&
          recommendedTemplateInfo.op_name === template.op_name
        ) {
          return null;
        }
        return (
          <DashboardTemplate
            key={template.op_name}
            title={template.display_name}
            subtitle={template.description}
            onButtonClick={() => {
              setIsGenerating(true);
              makeBoardFromNode(
                template.op_name,
                refinedExpression.result as any,
                newDashExpr => {
                  setIsGenerating(false);
                  navigateToExpression(newDashExpr);
                }
              );
            }}
            onClick={() => {
              setExpandedTemplate(template.op_name);
              const templateName = processTemplateNameForTracking(
                template.display_name
              );
              trackNewBoardFromTemplateClicked(
                'table-template-tab',
                templateName
              );
            }}
            isExpanded={expandedTemplate === template.op_name}
          />
        );
      })}
    </LayoutElements.VStack>
  );
};

const DashboardTemplate: React.FC<{
  title?: string;
  onClick?: () => void;
  isRecommended?: boolean;
  subtitle?: string;
  isExpanded?: boolean;
  buttonVariant?: 'primary' | 'secondary';
  buttonText?: string;
  onButtonClick?: () => void;
}> = ({
  title,
  onClick,
  onButtonClick,
  subtitle,
  isExpanded = false,
  buttonVariant = 'primary',
  buttonText = 'New board from template',
  isRecommended = false,
}) => {
  return (
    <DashboardTemplateItem onClick={onClick}>
      <LayoutElements.VStack
        style={{
          overflow: 'hidden',
        }}>
        {isRecommended && (
          <LayoutElements.Block
            style={{
              marginBottom: '8px',
            }}>
            <Pill label="Recommended template" color="green" />
          </LayoutElements.Block>
        )}
        {title && (
          <DashboardTemplateItemText
            style={{
              fontWeight: 600,
              fontSize: '16px',
              lineHeight: '24px',
              color: MOON_800,
            }}>
            {title}
          </DashboardTemplateItemText>
        )}
        {subtitle && (
          <DashboardTemplateItemText
            style={{
              fontSize: '14px',
              fontWeight: '400',
              lineHeight: '20px',
              color: MOON_500,
            }}>
            {subtitle}
          </DashboardTemplateItemText>
        )}
        {isExpanded && (
          <LayoutElements.Block
            style={{
              marginTop: '8px',
            }}>
            <Button
              icon="add-new"
              variant={buttonVariant}
              onClick={onButtonClick}
              size="large"
              className="w-full">
              {buttonText}
            </Button>
          </LayoutElements.Block>
        )}
      </LayoutElements.VStack>
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

function processTemplateNameForTracking(templateName: string) {
  return templateName.toLowerCase().trim().split(' ').join('_');
}
