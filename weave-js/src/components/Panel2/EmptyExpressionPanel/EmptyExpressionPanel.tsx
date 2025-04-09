import {
  EditingNode,
  isAssignableTo,
  list,
  Node,
  NodeOrVoidNode,
  pushFrame,
  varNode,
} from '@wandb/weave/core';
import React, {useLayoutEffect, useMemo, useRef, useState} from 'react';

import {Icon, IconName, IconNames} from '../../Icon';
import {usePanelContext} from '../PanelContext';
import {inputType} from '../PanelExpression/common';
import {makeEventRecorder} from '../panellib/libanalytics';
import * as S from './EmptyExpressionPanel.styles';
import {PickCard} from './PickCard';
import {runConfig, runHistory, runSummary} from './shortcutExpressions';
import {
  runConfigExpressionText,
  runHistoryExpressionText,
  runSummaryExpressionText,
} from './util';

const recordEvent = makeEventRecorder('EmptyPanelShortcut');

type CardAction = {
  title: string;
  id: string;
  outputNodeFn: (inputNode: Node) => EditingNode;
  icon: IconName;
  expressionText: ExpressionTextItem[];
};

const BASIC_CARD_ACTIONS: CardAction[] = [
  {
    id: 'RUN_CONFIG_TABLE',
    title: 'Explore configuration',
    expressionText: runConfigExpressionText,
    outputNodeFn: inputNode => runConfig(inputNode),
    icon: IconNames.SettingsParameters,
  },
  {
    id: 'RUN_SUMMARY_TABLE',
    title: 'View run summaries',
    expressionText: runSummaryExpressionText,
    outputNodeFn: inputNode => runSummary(inputNode),
    icon: IconNames.Table,
  },
  {
    id: 'RUN_HISTORY_TABLE',
    title: 'View run history',
    expressionText: runHistoryExpressionText,
    outputNodeFn: inputNode => runHistory(inputNode),
    icon: IconNames.BookDictionary,
  },
];

interface EmptyExpressionPanelProps {
  updateExp: (newExp: EditingNode) => void;
  inputNode: NodeOrVoidNode<typeof inputType>;
  newVars: {[key: string]: Node<'any'>};
}

interface ExpressionTextItem {
  text: string;
  color: string;
}

export const EmptyExpressionPanel: React.FC<
  EmptyExpressionPanelProps
> = props => {
  const {updateExp, inputNode, newVars} = props;
  const panelContext = usePanelContext();
  const stack = useMemo(() => {
    return pushFrame(panelContext.stack, newVars);
  }, [newVars, panelContext.stack]);

  const headerRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [headerDimensions, setHeaderDimensions] = useState({
    height: 120,
  });
  const [shouldScroll, setShouldScroll] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);

  useLayoutEffect(() => {
    const resizeObserver = new ResizeObserver(() => {
      window.requestAnimationFrame(() => {
        if (headerRef.current && containerRef.current) {
          const {height} = headerRef.current.getBoundingClientRect();
          const computedStyle = window.getComputedStyle(headerRef.current);
          const marginTop = parseInt(computedStyle.marginTop, 10) || 0;
          const marginBottom = parseInt(computedStyle.marginBottom, 10) || 0;
          const paddingBottom = parseInt(computedStyle.paddingBottom, 10) || 0;

          const bufferSpace = 16;
          const totalHeaderHeight =
            Math.ceil(height) +
            marginTop +
            marginBottom +
            paddingBottom +
            bufferSpace;

          setHeaderDimensions({
            height: totalHeaderHeight,
          });

          const containerHeight = containerRef.current.clientHeight;
          setShouldScroll(containerHeight - totalHeaderHeight < 300);
        }
      });
    });

    if (headerRef.current) {
      const {height} = headerRef.current.getBoundingClientRect();
      const computedStyle = window.getComputedStyle(headerRef.current);
      const marginTop = parseInt(computedStyle.marginTop, 10) || 0;
      const marginBottom = parseInt(computedStyle.marginBottom, 10) || 0;
      const paddingBottom = parseInt(computedStyle.paddingBottom, 10) || 0;
      const bufferSpace = 16;

      const totalHeight =
        Math.ceil(height) +
        marginTop +
        marginBottom +
        paddingBottom +
        bufferSpace;

      setHeaderDimensions({
        height: totalHeight,
      });

      resizeObserver.observe(headerRef.current);
    }

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    // Observe parent elements to catch panel resizing
    let parentElement: HTMLElement | null = headerRef.current;
    if (parentElement) {
      while (parentElement.parentElement) {
        parentElement = parentElement.parentElement;
        resizeObserver.observe(parentElement);

        if (
          parentElement.classList.contains('panel-inner') ||
          parentElement.tagName === 'BODY'
        ) {
          break;
        }
      }
    }

    setIsInitialized(true);

    return () => resizeObserver.disconnect();
  }, []);

  const handleCardClick = (action: CardAction) => {
    const runsValFromStack = stack.find(s => s.name === 'runs');
    if (!runsValFromStack) {
      return;
    }

    updateExp(
      action.outputNodeFn(varNode(runsValFromStack.value.type, 'runs'))
    );

    recordEvent('SELECT_SHORTCUT', {name: action.title});
  };

  if (!inputNode || !isAssignableTo(inputNode?.type, list('run'))) {
    return <></>;
  }

  return (
    <S.Container ref={containerRef}>
      <S.HeaderSection ref={headerRef}>
        <S.SearchIconContainer className={`my-8 rounded-full bg-[#A9EDF2]`}>
          <S.SearchIcon name={IconNames.Search} className={`text-[#13a9ba]`} />
        </S.SearchIconContainer>
        <S.Title>START WITH AN EXPRESSION</S.Title>
        <S.Subtitle>
          <span>
            Enter a query expression to explore your data or choose from common
            queries
          </span>
        </S.Subtitle>
      </S.HeaderSection>
      <S.DynamicScrollContainer
        headerHeight={headerDimensions.height}
        shouldScroll={shouldScroll}
        isInitialized={isInitialized}>
        <S.CardGrid>
          <PickCard updateExp={updateExp} stack={stack} />
          {BASIC_CARD_ACTIONS.map(action => (
            <S.Card
              key={action.id}
              onClick={() => handleCardClick(action)}
              role="button"
              aria-label={`Select ${action.title}`}>
              <S.CardTitleContainer>
                <Icon name={action.icon} />
                <S.CardTitle>{action.title}</S.CardTitle>
              </S.CardTitleContainer>

              <S.CardSubtitle>
                <S.ExpressionWrapper>
                  {action.expressionText.map((item, index) => (
                    <React.Fragment key={index}>
                      <span style={{color: item.color}}>{item.text}</span>
                    </React.Fragment>
                  ))}
                </S.ExpressionWrapper>
              </S.CardSubtitle>
            </S.Card>
          ))}
        </S.CardGrid>
      </S.DynamicScrollContainer>
    </S.Container>
  );
};
