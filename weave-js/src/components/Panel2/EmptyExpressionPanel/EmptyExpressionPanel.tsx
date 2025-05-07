import {
  isAssignableTo,
  list,
  Node,
  NodeOrVoidNode,
  pushFrame,
} from '@wandb/weave/core';
import React, {
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import {Icon, IconName, IconNames} from '../../Icon';
import {usePanelContext} from '../PanelContext';
import {inputType} from '../PanelExpression/common';
import {makeEventRecorder} from '../panellib/libanalytics';
import * as S from './EmptyExpressionPanel.styles';
import {
  runConfigExpressionText,
  runHistoryExpressionText,
  runSummaryExpressionText,
  runSummaryKeyExpressionText,
} from './util';

const recordEvent = makeEventRecorder('EmptyPanelShortcut');

type CardAction = {
  title: string;
  id: string;
  icon: IconName;
  expressionText: ExpressionTextItem[];
  cursorPos?: {
    offset?: number;
  };
};

const BASIC_CARD_ACTIONS: CardAction[] = [
  {
    id: 'RUN_CONFIG_TABLE',
    title: 'Explore configuration',
    expressionText: runConfigExpressionText,
    icon: IconNames.SettingsParameters,
  },
  {
    id: 'RUN_SUMMARY_TABLE',
    title: 'View run summaries',
    expressionText: runSummaryExpressionText,
    icon: IconNames.Table,
  },
  {
    id: 'RUN_HISTORY_TABLE',
    title: 'View run history',
    expressionText: runHistoryExpressionText,
    icon: IconNames.List,
  },
  {
    id: 'RUN_SUMMARY_KEY_TABLE',
    title: 'View summary key',
    expressionText: runSummaryKeyExpressionText,
    icon: IconNames.Table,
    cursorPos: {
      offset: -2,
    },
  },
];

interface EmptyExpressionPanelProps {
  inputNode: NodeOrVoidNode<typeof inputType>;
  newVars: {[key: string]: Node<'any'>};
  insertTextIntoEditor?: (
    text: string,
    options?: {
      offset?: number;
    }
  ) => void;
}

interface ExpressionTextItem {
  text: string;
  color: string;
}

export const EmptyExpressionPanel: React.FC<
  EmptyExpressionPanelProps
> = props => {
  const {inputNode, newVars, insertTextIntoEditor} = props;
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
  const [gridColumns, setGridColumns] = useState(1);

  // Directly track container width for compact mode determination
  const [containerWidth, setContainerWidth] = useState(0);

  // Determine if compact mode is active based on width
  const isCompactMode = containerWidth < 240;

  // Update grid columns based on container width
  const updateGridColumns = useCallback((width: number) => {
    if (width >= 500) {
      setGridColumns(3);
    } else if (width >= 380) {
      setGridColumns(2);
    } else {
      setGridColumns(1);
    }
  }, []);

  // Update measurements when resizing
  const updateContainerMeasurements = useCallback(
    (width: number) => {
      setContainerWidth(width);
      updateGridColumns(width);
    },
    [updateGridColumns]
  );

  // Create a grid template style based on columns
  const cardContainerStyle = React.useMemo(() => {
    return {
      gridTemplateColumns: `repeat(${gridColumns}, 1fr)`,
      width: '100%',
      maxWidth: '900px',
      gap: '8px',
      marginTop: isCompactMode ? '0' : '12px',
      paddingBottom: '8px',
    };
  }, [gridColumns, isCompactMode]);

  useLayoutEffect(() => {
    const resizeObserver = new ResizeObserver(() => {
      window.requestAnimationFrame(() => {
        if (headerRef.current && containerRef.current) {
          const {height} = headerRef.current.getBoundingClientRect();
          const computedStyle = window.getComputedStyle(headerRef.current);
          const marginTop = parseInt(computedStyle.marginTop, 10) || 0;
          const marginBottom = parseInt(computedStyle.marginBottom, 10) || 0;
          const paddingBottom = parseInt(computedStyle.paddingBottom, 10) || 0;

          let totalHeaderHeight;
          if (isCompactMode) {
            totalHeaderHeight = 40;
          } else {
            const bufferSpace = 16;
            totalHeaderHeight =
              Math.ceil(height) +
              marginTop +
              marginBottom +
              paddingBottom +
              bufferSpace;
          }

          setHeaderDimensions({
            height: totalHeaderHeight,
          });

          const width = containerRef.current.clientWidth;
          updateContainerMeasurements(width);

          const containerHeight = containerRef.current.clientHeight;
          setShouldScroll(
            isCompactMode ? false : containerHeight - totalHeaderHeight < 300
          );
        }
      });
    });

    if (headerRef.current) {
      const {height} = headerRef.current.getBoundingClientRect();
      const computedStyle = window.getComputedStyle(headerRef.current);
      const marginTop = parseInt(computedStyle.marginTop, 10) || 0;
      const marginBottom = parseInt(computedStyle.marginBottom, 10) || 0;
      const paddingBottom = parseInt(computedStyle.paddingBottom, 10) || 0;

      let totalHeight;
      if (isCompactMode) {
        totalHeight = 40;
      } else {
        const bufferSpace = 16;
        totalHeight =
          Math.ceil(height) +
          marginTop +
          marginBottom +
          paddingBottom +
          bufferSpace;
      }

      setHeaderDimensions({
        height: totalHeight,
      });

      resizeObserver.observe(headerRef.current);
    }

    if (containerRef.current) {
      // Initial width measurement
      const width = containerRef.current.clientWidth;
      updateContainerMeasurements(width);

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
  }, [isCompactMode, updateContainerMeasurements]);

  const handleCardClick = (action: CardAction) => {
    const runsValFromStack = stack.find(s => s.name === 'runs');
    if (!runsValFromStack) {
      return;
    }

    if (insertTextIntoEditor) {
      const expressionText = action.expressionText
        .map(item => item.text)
        .join('');

      if (action.cursorPos) {
        insertTextIntoEditor(expressionText, action.cursorPos);
      } else {
        insertTextIntoEditor(expressionText);
      }
    }

    recordEvent(`SELECT_SHORTCUT_${action.id}`);
  };

  if (!inputNode || !isAssignableTo(inputNode?.type, list('run'))) {
    return <></>;
  }

  return (
    <S.Container ref={containerRef}>
      <S.HeaderSection ref={headerRef}>
        {!isCompactMode && (
          <div
            style={{
              height: '40px',
              width: '40px',
              backgroundColor: 'rgba(169, 237, 242, 0.48)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              aspectRatio: 1,
              borderRadius: '9999px',
              marginBottom: '8px',
            }}>
            <Icon
              name={IconNames.Search}
              style={{height: '24px', width: '24px', color: '#038194'}}
            />
          </div>
        )}
        <S.Title>START WITH AN EXPRESSION</S.Title>
        {!isCompactMode && (
          <S.Subtitle>
            <span>
              Enter a query expression or choose from common queries to explore
              your data
            </span>
          </S.Subtitle>
        )}
      </S.HeaderSection>
      <S.DynamicScrollContainer
        headerHeight={headerDimensions.height}
        shouldScroll={shouldScroll}
        isInitialized={isInitialized}>
        <S.CardGrid style={cardContainerStyle}>
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

              {!isCompactMode && (
                <S.CardSubtitle>
                  <S.ExpressionWrapper>
                    {action.expressionText.map((item, index) => (
                      <React.Fragment key={index}>
                        <span style={{color: item.color}}>{item.text}</span>
                      </React.Fragment>
                    ))}
                  </S.ExpressionWrapper>
                </S.CardSubtitle>
              )}
            </S.Card>
          ))}
        </S.CardGrid>
      </S.DynamicScrollContainer>
    </S.Container>
  );
};
