import {toast} from '@wandb/weave/common/components/elements/Toast';
import * as globals from '@wandb/weave/common/css/globals.styles';
import React, {
  ComponentType,
  FC,
  MutableRefObject,
  PropsWithChildren,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import ReactDOM from 'react-dom';
import {Button, Ref} from 'semantic-ui-react';
import styled from 'styled-components';

import {IconCopy, IconFullScreenModeExpand} from './Icons';
import {PanelFullscreenContext} from './PanelComp';

export const HOVER_DELAY_MS = 200;

// Invisible area around tooltip that helps prevent spurious close events
const TT_MARGIN_PX = 12;

const TriggerWrapper = styled.div`
  width: 100%;
  height: 100%;
  overflow: auto;

  // Hide scrollbars
  &::-webkit-scrollbar {
    display: none;
  }
  -ms-overflow-style: none; /* IE and Edge */
  scrollbar-width: none; /* Firefox */

  &&&.tooltip-open > * {
    background-color: ${globals.GOLD_LIGHT}29; /* 16% opacity */
  }
`;
TriggerWrapper.displayName = 'S.TriggerWrapper';

type Anchor = 'topleft' | 'topright' | 'bottomleft' | 'bottomright';
type Direction = 'horizontal' | 'vertical';

const TooltipWrapper = styled.div<{
  position: TooltipPosition;
  padding: number;
}>`
  position: absolute;

  background: none;

  // So we have some extra margin around the popup menu's visible
  // area before it closes due to mouse leaving
  padding: ${props => props.padding}px;
  left: ${props => props.position.x}px;
  top: ${props => props.position.y}px;
  transform: ${props => {
    // anchor is w/r/t the tooltip, not the anchor
    // eg, bottomleft means the bottom left corner of the tooltip is touching the content
    switch (props.position.anchor) {
      case 'topleft':
        return `translate(-${props.padding}px, -${props.padding}px)`;
      case 'topright':
        return `translate(-100%, 0%) translate(${props.padding}px, -${props.padding}px)`;
      case 'bottomleft':
        return `translate(0%, -100%) translate(-${props.padding}px, ${props.padding}px)`;
      case 'bottomright':
        return `translate(-100%, -100%) translate(${props.padding}px, ${props.padding}px)`;
      default:
        return `none`;
    }
  }};

  // The modal z-index is 2147483605, so this needs to be higher
  // for the tooltip to properly show in fullscreen mode.
  z-index: 2147483606;
`;
TooltipWrapper.displayName = 'S.TooltipWrapper';

const TooltipFrame = styled.div`
  background: white;
  border-radius: 4px;
  border: 1px solid ${globals.GRAY_350};
  box-shadow: 0px 8px 16px ${globals.OBLIVION}1F;

  min-width: 300px;
  max-width: 45vw;
  max-height: 45vh;

  padding: 0px;

  display: flex;
  flex-direction: column;
  overflow: hidden;
`;
TooltipFrame.displayName = 'S.TooltipFrame';

const TooltipHeaderText = styled.span`
  font-size: 16px;
  font-weight: 600;
  line-height: 22.4px;
`;
TooltipHeaderText.displayName = 'S.TooltipHeaderText';

const TooltipButtons = styled.div`
  display: flex;
  flex-direction: row;
  align-items: center;

  &&& button {
    background-color: transparent;
    color: ${globals.GRAY_800}:;
    width: 24px;
    height: 24px;
    border: none;
    margin: 4px;
    padding: 4px;

    svg {
      width: 16px;
      height: 16px;
      color: inherit;
      stroke-width: 1;
    }
  }

  &&& button.extra-button {
    font-size: 16px;
    font-weight: 600;
    line-height: 22.4px;
    width: fit-content;
    margin: 0px;
    margin-left: 24px;
    padding: 0px 4px;
    color: ${globals.TEAL_DARK};
  }

  &&& button:hover {
    background-color: ${globals.TEAL_TRANSPARENT_2};
    color: ${globals.TEAL};
  }
`;
TooltipButtons.displayName = 'S.TooltipButtons';

const TooltipHeader = styled.div`
  padding: 0px 16px;
  height: 56px;
  flex-shrink: 0;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid ${globals.GRAY_350};
`;
TooltipHeader.displayName = 'S.TooltipHeader';

const TooltipBody = styled.div`
  padding: 12px 16px;
  font-size: 14px;
  line-height: 20px;
  overflow-y: scroll;
  &&& pre {
    margin-top: 0px;
    margin-bottom: 0px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  &&& .markdown {
    font-size: 14px;
  }
`;
TooltipBody.displayName = 'S.TooltipBody';

interface TooltipPosition {
  x: number;
  y: number;
  anchor?: Anchor;
  direction?: Direction;
}

type TooltipPositionStrategy = (anchorRect: DOMRect) => TooltipPosition;

const POSITION_STRATEGIES: Readonly<TooltipPositionStrategy[]> = [
  // expand vertically away
  (anchorRect: DOMRect): TooltipPosition => ({
    anchor: 'bottomleft',
    direction: 'vertical',
    x: anchorRect.left + window.scrollX,
    y: anchorRect.top + window.scrollY,
  }),
  (anchorRect: DOMRect): TooltipPosition => ({
    anchor: 'bottomright',
    direction: 'vertical',
    x: anchorRect.right + window.scrollX,
    y: anchorRect.top + window.scrollY,
  }),
  (anchorRect: DOMRect): TooltipPosition => ({
    anchor: 'topleft',
    direction: 'vertical',
    x: anchorRect.left + window.scrollX,
    y: anchorRect.bottom + window.scrollY,
  }),
  (anchorRect: DOMRect): TooltipPosition => ({
    anchor: 'topright',
    direction: 'vertical',
    x: anchorRect.right + window.scrollX,
    y: anchorRect.bottom + window.scrollY,
  }),

  // expand horizontally away
  (anchorRect: DOMRect): TooltipPosition => ({
    anchor: 'topleft',
    direction: 'horizontal',
    x: anchorRect.right + window.scrollX,
    y: anchorRect.top + window.scrollY,
  }),
  (anchorRect: DOMRect): TooltipPosition => ({
    anchor: 'bottomleft',
    direction: 'horizontal',
    x: anchorRect.right + window.scrollX,
    y: anchorRect.bottom + window.scrollY,
  }),
  (anchorRect: DOMRect): TooltipPosition => ({
    anchor: 'topright',
    direction: 'horizontal',
    x: anchorRect.left + window.scrollX,
    y: anchorRect.top + window.scrollY,
  }),
  (anchorRect: DOMRect): TooltipPosition => ({
    anchor: 'bottomright',
    direction: 'horizontal',
    x: anchorRect.left + window.scrollX,
    y: anchorRect.bottom + window.scrollY,
  }),
] as const;

const calcTooltipRect = (
  params: TooltipPosition,
  tooltipRect: DOMRect
): DOMRect => {
  const {width: ttWidth, height: ttHeight} = tooltipRect;
  switch (params.anchor) {
    case 'topleft':
      return new DOMRect(params.x, params.y, ttWidth, ttHeight);
    case 'topright':
      return new DOMRect(params.x - ttWidth, params.y, ttWidth, ttHeight);
    case 'bottomleft':
      return new DOMRect(params.x, params.y - ttHeight, ttWidth, ttHeight);
    case 'bottomright':
      return new DOMRect(
        params.x - ttWidth,
        params.y - ttHeight,
        ttWidth,
        ttHeight
      );
    default:
      throw new Error(`calcTooltipRect called without valid anchor`);
  }
};

const getTooltipPositionScore = (
  params: TooltipPosition,
  rawTooltipRect: DOMRect
): number => {
  const tooltipRect = calcTooltipRect(params, rawTooltipRect);
  const viewportRect = new DOMRect(
    window.scrollX,
    window.scrollY,
    window.innerWidth,
    window.innerHeight
  );

  // Calculate the width and height of intersection between tooltipRect and viewportRect
  const xWidth =
    Math.min(tooltipRect.right, viewportRect.right) -
    Math.max(tooltipRect.left, viewportRect.left);
  const xHeight =
    Math.min(tooltipRect.bottom, viewportRect.bottom) -
    Math.max(tooltipRect.top, viewportRect.top);

  // The score is the size of the intersection divided by the size of the tooltip
  return (xWidth * xHeight) / (tooltipRect.width * tooltipRect.height);
};

const getTooltipPosition = (
  anchorRect: DOMRect,
  tooltipRect: DOMRect
): TooltipPosition => {
  const scoredPositions = POSITION_STRATEGIES.map(strategy => {
    const position = strategy(anchorRect);
    const score = getTooltipPositionScore(position, tooltipRect);
    return {...position, score};
  });

  const bestPosition = scoredPositions.reduce(
    (best, current) => (current.score > best.score ? current : best),
    scoredPositions[0]
  );

  return bestPosition;
};

const TooltipContent: FC<{
  anchor: HTMLElement;
  content: ReactNode;
  close: () => void;
  copy: () => void;
  expand: () => void;
  extraButton?: TooltipExtraButtonData;
  contentHeight?: number;
  noHeader?: boolean;
  padding?: number;
  positionNearMouse?: boolean;
  lastMousePositionRef?: MutableRefObject<TooltipPosition | undefined>;
  FrameComp?: ComponentType;
  BodyComp?: ComponentType;
}> = ({
  anchor,
  content,
  close,
  copy,
  expand,
  extraButton,
  contentHeight,
  noHeader = false,
  padding = TT_MARGIN_PX,
  positionNearMouse = false,
  lastMousePositionRef,
  FrameComp = TooltipFrame,
  BodyComp = TooltipBody,
}) => {
  const [position, setPosition] = useState<TooltipPosition | null>(null);
  const [containerRef, setContainerRef] = useState<HTMLDivElement | null>(null);

  useLayoutEffect(() => {
    if (containerRef == null || positionNearMouse) {
      return;
    }

    const bestPosition = getTooltipPosition(
      anchor.getBoundingClientRect(),
      containerRef.getBoundingClientRect()
    );
    setPosition(bestPosition);
    // contentHeight is not used but is useful for triggering recalculation,
    // especially in the case of a markdown preview
  }, [positionNearMouse, anchor, containerRef, contentHeight]);

  useEffect(() => {
    if (!positionNearMouse) {
      return;
    }

    const lastMousePosition = lastMousePositionRef?.current;
    if (lastMousePosition != null) {
      setPosition(addBufferToMouseBasedPosition(lastMousePosition));
    }

    document.addEventListener(`mousemove`, onMouseMove);
    return () => {
      document.removeEventListener(`mousemove`, onMouseMove);
    };

    function onMouseMove(e: MouseEvent): void {
      if (containerRef == null) {
        return;
      }
      const {x, y} = addBufferToMouseBasedPosition({
        x: e.clientX,
        y: e.clientY,
      });
      containerRef.style.left = `${x}px`;
      containerRef.style.top = `${y}px`;
    }
  }, [positionNearMouse, containerRef, lastMousePositionRef]);

  // Need to draw offscreen so we can measure and figure out
  // what position actually needs to be
  return ReactDOM.createPortal(
    <Ref innerRef={setContainerRef}>
      <TooltipWrapper
        className="weave-tooltip"
        position={
          position ?? {
            x: -10000,
            y: -10000,
          }
        }
        padding={padding}
        onMouseLeave={close}>
        <FrameComp>
          {!noHeader && (
            <TooltipHeader>
              <TooltipHeaderText>Preview</TooltipHeaderText>
              <TooltipButtons>
                {extraButton && (
                  <Button
                    className="extra-button"
                    size="mini"
                    compact
                    onClick={extraButton.callback}>
                    {extraButton.label}
                  </Button>
                )}
                <Button size="mini" compact onClick={copy}>
                  <IconCopy />
                </Button>
                <Button size="mini" compact onClick={expand}>
                  <IconFullScreenModeExpand />
                </Button>
              </TooltipButtons>
            </TooltipHeader>
          )}
          <BodyComp>{content}</BodyComp>
        </FrameComp>
      </TooltipWrapper>
    </Ref>,
    document.body
  );
};

export interface TooltipExtraButtonData {
  label: string;
  callback: () => void;
}

export const TooltipTrigger: FC<
  PropsWithChildren<{
    content: ReactNode;
    copyableContent?: string;
    extraButton?: TooltipExtraButtonData;
    triggerContentHeight?: number;
    showWithoutOverflow?: boolean;
    showInFullscreen?: boolean;
    noHeader?: boolean;
    padding?: number;
    positionNearMouse?: boolean;
    TriggerWrapperComp?: ComponentType;
    FrameComp?: ComponentType;
    BodyComp?: ComponentType;
  }>
> = ({
  children,
  content,
  copyableContent,
  extraButton,
  triggerContentHeight,
  showWithoutOverflow = false,
  showInFullscreen = false,
  noHeader = false,
  padding,
  positionNearMouse = false,
  TriggerWrapperComp = TriggerWrapper,
  FrameComp,
  BodyComp,
}) => {
  const openTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const {isFullscreen, goFullscreen} = useContext(PanelFullscreenContext);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [hovering, setHovering] = useState(false);
  const [isOpen, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);

  const anchorHeight = anchor?.clientHeight ?? 0;
  const anchorWidth = anchor?.clientWidth ?? 0;
  useEffect(() => {
    // Check if the content is overflowing. Can't use the naive approach
    // clientHeight vs scrollHeight because of the way we're rendering
    // the content (nested divs w/ hidden overflow) so we must manually check
    // the client heights of descendants.
    if (anchor == null) {
      return;
    }
    const overflowing = Array.from(anchor.querySelectorAll('pre, div')).some(
      e => {
        return (
          (triggerContentHeight ?? 0) > anchorHeight ||
          e.clientHeight > anchorHeight ||
          e.scrollHeight > anchorHeight ||
          e.clientWidth > anchorWidth ||
          e.scrollWidth > anchorWidth
        );
      }
    );
    setIsOverflowing(overflowing);
  }, [anchor, anchorHeight, anchorWidth, content, triggerContentHeight]);

  const copyToClipboard = useCallback(() => {
    if (copyableContent == null) {
      return;
    }
    navigator.clipboard.writeText(copyableContent);
    toast('Copied to clipboard', {type: 'success'});
  }, [copyableContent]);

  const entered = useCallback(() => {
    setHovering(true);
  }, []);

  const exited = useCallback(
    (e: React.MouseEvent) => {
      if (openTimeout.current != null) {
        clearTimeout(openTimeout.current);
        openTimeout.current = null;
      }
      setHovering(false);
      if (isOpen) {
        // Close the tooltip only when the mouse leaves for a target
        // that is NOT the tooltip or a descendant of the tooltip.
        let target = e.relatedTarget as HTMLElement;
        while (target != null && target.nodeName !== 'BODY') {
          if (target.classList?.contains('weave-tooltip')) {
            return;
          }
          target = target.parentElement as HTMLElement;
        }
        setOpen(false);
      }
    },
    [isOpen]
  );

  const lastMousePositionRef = useRef<TooltipPosition | undefined>(undefined);
  const handleMove = useCallback(
    (e: React.MouseEvent) => {
      lastMousePositionRef.current = {x: e.clientX, y: e.clientY};
      if (openTimeout.current != null) {
        clearTimeout(openTimeout.current);
        openTimeout.current = null;
      }
      openTimeout.current = setTimeout(() => {
        if (hovering) {
          setOpen(true);
        }
      }, HOVER_DELAY_MS);
    },
    [hovering]
  );

  const handleClose = useCallback(() => {
    setOpen(false);
  }, []);
  const handleExpand = useCallback(() => {
    goFullscreen();
    handleClose();
  }, [goFullscreen, handleClose]);

  const showTooltip =
    (showWithoutOverflow || isOverflowing) &&
    (showInFullscreen || !isFullscreen) &&
    isOpen &&
    anchor != null;

  return (
    <>
      <TriggerWrapperComp
        onMouseEnter={entered}
        onMouseLeave={exited}
        onMouseMove={handleMove}
        ref={setAnchor}
        className={showTooltip ? 'tooltip-open' : ''}>
        {children}
      </TriggerWrapperComp>
      {showTooltip && (
        <TooltipContent
          anchor={anchor}
          content={content}
          contentHeight={triggerContentHeight}
          close={handleClose}
          copy={copyToClipboard}
          expand={handleExpand}
          extraButton={extraButton}
          noHeader={noHeader}
          padding={padding}
          positionNearMouse={positionNearMouse}
          lastMousePositionRef={lastMousePositionRef}
          FrameComp={FrameComp}
          BodyComp={BodyComp}
        />
      )}
    </>
  );
};

function addBufferToMouseBasedPosition({
  x,
  y,
  ...rest
}: TooltipPosition): TooltipPosition {
  return {
    ...rest,
    x: x + window.scrollX + 24,
    y: y + window.scrollY,
  };
}
