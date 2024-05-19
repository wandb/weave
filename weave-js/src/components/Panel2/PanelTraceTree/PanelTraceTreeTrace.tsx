import * as globals from '@wandb/weave/common/css/globals.styles';
import {SpanType} from '@wandb/weave/core/model/media/traceTree';
import React, {useCallback, useMemo} from 'react';
import {Loader} from 'semantic-ui-react';
import styled from 'styled-components';

import {useUpdatingState} from '../../../hookUtils';
import {useNodeValue} from '../../../react';
import * as Panel2 from '../panel';
import {PanelFullscreenContext} from '../PanelComp';
import {TooltipTrigger} from '../Tooltip';
import {getSpanDuration, getSpanIdentifier, getSpanKindStyle} from './common';
import {
  LayedOutSpanType,
  LayedOutSpanWithParentYLevel,
  layoutTree,
} from './layout';
import * as S from './lct.style';
import {SpanTreeDetail} from './PanelTraceSpan';
import {useTipOverlay} from './tipOverlay';
import {treesToFlat} from './util';
import {useTimelineZoomAndPan} from './zoomAndPan';

const inputType = {
  type: 'wb_trace_tree' as const,
};

type PanelTraceTreeTraceConfigType = {};

type PanelTraceTreeTraceProps = Panel2.PanelProps<
  typeof inputType,
  PanelTraceTreeTraceConfigType
>;

const PanelTraceTreeTrace: React.FC<PanelTraceTreeTraceProps> = props => {
  const nodeValue = useNodeValue(props.input);
  const [traceSpan, setTraceSpan] = React.useState<null | SpanType>(null);
  React.useEffect(() => {
    if (nodeValue.result) {
      try {
        const rootSpan = JSON.parse(
          nodeValue.result.root_span_dumps
        ) as SpanType;
        setTraceSpan(rootSpan);
      } catch (e) {
        console.log(e);
      }
    }
  }, [nodeValue.result]);

  if (nodeValue.loading) {
    return <Loader />;
  }

  if (traceSpan == null) {
    return <div></div>;
  }

  return <TraceTreeSpanViewer span={traceSpan} />;
};

export const TraceTreeSpanViewer: React.FC<{
  span: SpanType;
  onSelectSpanIndex?: (spanIndex: number) => void;
  selectedSpanIndex?: number | null;
  hideDetails?: boolean;
}> = props => {
  const {isFullscreen} = React.useContext(PanelFullscreenContext);
  const split = isFullscreen ? `horizontal` : `vertical`;

  const span = props.span;

  const {tipOverlay, showTipOverlay} = useTipOverlay();

  const layedOutSpan = useMemo(() => {
    return layoutTree(span);
  }, [span]);
  const flatSpans = useMemo(() => treesToFlat([layedOutSpan]), [layedOutSpan]);

  const {timelineRef, timelineStyle, scale} = useTimelineZoomAndPan({
    onHittingMinZoom: showTipOverlay,
  });

  const [selectedSpanUncontrolled, setSelectedSpanUncontrolled] =
    useUpdatingState<LayedOutSpanType | null>(layedOutSpan);

  const setSelectedSpan = useCallback(
    (newSelectedSpan: LayedOutSpanType | null) => {
      if (props.onSelectSpanIndex != null) {
        if (newSelectedSpan != null && newSelectedSpan._span_index != null) {
          props.onSelectSpanIndex(newSelectedSpan._span_index);
        }
      } else {
        setSelectedSpanUncontrolled(newSelectedSpan);
      }
    },
    [props, setSelectedSpanUncontrolled]
  );

  const selectedSpan = useMemo(() => {
    if (props.onSelectSpanIndex != null) {
      if (props.selectedSpanIndex != null) {
        return flatSpans.find(
          innerSpan => innerSpan._span_index === props.selectedSpanIndex
        );
      }
      return flatSpans[0];
    }
    return selectedSpanUncontrolled;
  }, [
    flatSpans,
    props.onSelectSpanIndex,
    props.selectedSpanIndex,
    selectedSpanUncontrolled,
  ]);

  return (
    <S.TraceWrapper split={split}>
      <S.TraceTimelineWrapper>
        <S.TraceTimeline
          ref={timelineRef}
          style={{
            ...timelineStyle,
          }}
          onClick={e => {
            e.stopPropagation();
          }}>
          <S.TraceTimelineScale
            style={{
              width: `${(scale ?? 1) * 100}%`,
            }}>
            <SpanElements
              spans={flatSpans}
              setSelectedSpan={setSelectedSpan}
              selectedSpan={selectedSpan ?? null}
            />
          </S.TraceTimelineScale>
        </S.TraceTimeline>
        {tipOverlay}
      </S.TraceTimelineWrapper>
      {!props.hideDetails && selectedSpan && (
        <S.TraceDetail>
          <SpanTreeDetail span={selectedSpan} />
        </S.TraceDetail>
      )}
    </S.TraceWrapper>
  );
};

const TooltipTriggerWrapper = styled.div`
  position: relative;

  &&&.tooltip-open:before {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    right: 0;
    background-color: ${globals.hexToRGB(globals.BLACK, 0.04)};
    pointer-events: none;
  }
`;

const TooltipFrame = styled.div`
  padding: 4px 8px;
  background-color: ${globals.WHITE};
  border: 1px solid ${globals.GRAY_200};
`;

const TooltipBody = styled.div`
  font-family: 'Inconsolata';
  font-size: 12px;
  line-height: 140%;
  white-space: nowrap;
`;

const TooltipLine = styled.div<{bold?: boolean; red?: boolean}>`
  ${p => p.bold && `font-weight: 600;`}
  ${p => p.red && `color: ${globals.RED_DARK};`}
`;

export const SpanElement: React.FC<{
  span: LayedOutSpanWithParentYLevel;
  selectedSpan: LayedOutSpanType | null;
  setSelectedSpan: (trace: LayedOutSpanType | null) => void;
}> = ({span, selectedSpan, setSelectedSpan}) => {
  const identifier = getSpanIdentifier(span);
  const trueDuration = getSpanDuration(span);

  const hasError = span.status_code === 'ERROR';
  const isSelected = selectedSpan === span;
  const kindStyle = getSpanKindStyle(span.span_kind);
  const executionOrder = span.attributes?.execution_order ?? null;

  const tooltipContent = useMemo(() => {
    return (
      <>
        <TooltipLine bold>{identifier}</TooltipLine>
        <TooltipLine>{kindStyle.label}</TooltipLine>
        {hasError && <TooltipLine red>Error</TooltipLine>}
        {trueDuration != null && (
          <TooltipLine red={hasError}>
            {/* Round to up to 3 significant digits */}
            {parseFloat(trueDuration.toFixed(3))}ms
          </TooltipLine>
        )}
      </>
    );
  }, [identifier, kindStyle.label, hasError, trueDuration]);

  // All spans are rendered as siblings in the dom, and laid out using absolute
  // positioning.
  return (
    <>
      <S.TraceTimelineElementWrapper
        style={{
          position: 'absolute',
          left: `${span.xStartFrac * 100}%`,
          width: `${span.xWidthFrac * 100}%`,
          top: span.yLevel * 32,
          height: span.yHeight * 32,
        }}>
        <TooltipTrigger
          content={tooltipContent}
          showWithoutOverflow
          showInFullscreen
          noHeader
          padding={0}
          positionNearMouse
          TriggerWrapperComp={TooltipTriggerWrapper}
          FrameComp={TooltipFrame}
          BodyComp={TooltipBody}>
          <S.SpanElementHeader
            hasError={hasError}
            isSelected={isSelected}
            backgroundColor={kindStyle.color}
            color={kindStyle.textColor}
            onClick={e => {
              e.stopPropagation();
              setSelectedSpan(isSelected ? null : span);
            }}>
            <S.SpanElementInner>
              <div>
                {executionOrder != null ? `${executionOrder}: ` : ''}
                {kindStyle.icon}
                {identifier}
              </div>
              {trueDuration != null && (
                <S.DurationLabel>
                  {/* Round to up to 3 significant digits */}
                  {parseFloat(trueDuration.toFixed(3))}ms
                </S.DurationLabel>
              )}
            </S.SpanElementInner>
          </S.SpanElementHeader>
        </TooltipTrigger>
      </S.TraceTimelineElementWrapper>
      {span.yLevel > span.parentYLevel + 1 && (
        <S.SpanParentConnector
          className={span.name}
          backgroundColor={kindStyle.color}
          style={{
            position: 'absolute',
            left: `${span.xStartFrac * 100}%`,
            width: 2,
            height: (span.yLevel - span.parentYLevel - 1) * 32,
            top: (span.parentYLevel + 1) * 32,
            bottom: span.yLevel * 32,
          }}
        />
      )}
    </>
  );
};

// Wrap in memo so zooming doesn't cause a re-render of all spans.
export const SpanElementsInner: React.FC<{
  spans: LayedOutSpanWithParentYLevel[];
  selectedSpan: LayedOutSpanType | null;
  setSelectedSpan: (trace: LayedOutSpanType | null) => void;
}> = ({spans, selectedSpan, setSelectedSpan}) => {
  return (
    <>
      {spans.map((span, i) => (
        <SpanElement
          key={i}
          span={span}
          setSelectedSpan={setSelectedSpan}
          selectedSpan={selectedSpan}
        />
      ))}
    </>
  );
};

export const SpanElements = React.memo(SpanElementsInner);

export const Spec: Panel2.PanelSpec = {
  id: 'wb_trace_tree-traceViewer',
  canFullscreen: true,
  Component: PanelTraceTreeTrace,
  inputType,
};
