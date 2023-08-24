import * as globals from '@wandb/weave/common/css/globals.styles';
import {SpanKindType, SpanType} from '@wandb/weave/core/model/media/traceTree';
import React, {ReactNode, useCallback, useMemo} from 'react';
import {Loader} from 'semantic-ui-react';
import styled from 'styled-components';

import {useUpdatingState} from '../../../hookUtils';
import {useNodeValue} from '../../../react';
import {AgentSVG, ChainSVG, LLMSVG, ToolSVG} from '../Icons';
import * as Panel2 from '../panel';
import {PanelFullscreenContext} from '../PanelComp';
import {TooltipTrigger} from '../Tooltip';
import {
  agentColor,
  agentTextColor,
  chainColor,
  chainTextColor,
  llmColor,
  llmTextColor,
  MinimalTooltip,
  toolColor,
  toolTextColor,
} from './common';
import * as S from './lct.style';
import {useTipOverlay} from './tipOverlay';
import {useTimelineZoomAndPan} from './zoomAndPan';
import {
  LayedOutSpanType,
  LayedOutSpanWithParentYLevel,
  layoutTree,
} from './layout';
import {treesToFlat} from './util';

const inputType = {
  type: 'wb_trace_tree' as const,
};

type PanelTraceTreeTraceConfigType = {};

type PanelTraceTreeTraceProps = Panel2.PanelProps<
  typeof inputType,
  PanelTraceTreeTraceConfigType
>;

type SpanKindStyle = {
  color: string;
  textColor: string;
  label: string;
  icon: ReactNode;
};

function getSpanKindStyle(kind?: SpanKindType): SpanKindStyle {
  switch (kind) {
    case 'CHAIN':
      return {
        color: chainColor,
        textColor: chainTextColor,
        label: `Chain`,
        icon: <ChainSVG />,
      };
    case 'AGENT':
      return {
        color: agentColor,
        textColor: agentTextColor,
        label: `Agent`,
        icon: <AgentSVG />,
      };
    case 'TOOL':
      return {
        color: toolColor,
        textColor: toolTextColor,
        label: `Tool`,
        icon: <ToolSVG />,
      };
    case 'LLM':
      return {
        color: llmColor,
        textColor: llmTextColor,
        label: `LLM`,
        icon: <LLMSVG />,
      };
    default:
      return {
        color: '#f3f3f3',
        textColor: '#494848',
        label: `Span`,
        icon: <></>,
      };
  }
}

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
  hideDetail?: boolean;
  onSelectSpanIndex?: (spanIndex: number) => void;
  selectedSpanIndex?: number | null;
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
    (span: LayedOutSpanType | null) => {
      if (props.onSelectSpanIndex != null) {
        if (span != null && span._span_index != null) {
          props.onSelectSpanIndex(span._span_index);
        }
      } else {
        setSelectedSpanUncontrolled(span);
      }
    },
    [props, setSelectedSpanUncontrolled]
  );

  const selectedSpan = useMemo(() => {
    if (props.onSelectSpanIndex != null) {
      if (props.selectedSpanIndex != null) {
        return flatSpans.find(
          span => span._span_index === props.selectedSpanIndex
        );
      }
      return flatSpans[0];
    } else {
      return selectedSpanUncontrolled;
    }
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
              selectedSpan={selectedSpan}
            />
          </S.TraceTimelineScale>
        </S.TraceTimeline>
        {tipOverlay}
      </S.TraceTimelineWrapper>
      {selectedSpan && !props.hideDetail && (
        <S.TraceDetail>
          <SpanTreeDetail span={selectedSpan} />
        </S.TraceDetail>
      )}
    </S.TraceWrapper>
  );
};

const getSpanIdentifier = (span: SpanType) => {
  return span.name ?? span._name ?? span.span_kind ?? 'Unknown';
};

const getSpanDuration = (span: SpanType) => {
  if (span.end_time_ms && span.start_time_ms) {
    return span.end_time_ms - span.start_time_ms;
  }
  return null;
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

const SpanTreeDetail: React.FC<{
  span: LayedOutSpanType;
}> = props => {
  const {span} = props;
  const kindStyle = getSpanKindStyle(span.span_kind);
  const identifier = getSpanIdentifier(span);
  const duration = getSpanDuration(span);

  return (
    <S.TraceDetailWrapper>
      <S.SpanDetailWrapper>
        <S.SpanDetailHeader>
          <span>
            <span
              style={{
                color: kindStyle.textColor,
              }}>
              {kindStyle.icon}
            </span>
            {identifier}
          </span>
          {duration != null && <S.DurationLabel>{duration}ms</S.DurationLabel>}
        </S.SpanDetailHeader>
        <S.SpanDetailTable>
          <tbody>
            {span.status_message != null && (
              <DetailKeyValueRow
                style={{
                  color: span.status_code === 'ERROR' ? '#EB1C45' : undefined,
                }}
                label="Status Message"
                value={span.status_message}
              />
            )}
            {span.results != null && (
              <>
                {span.results.map((result, i) => {
                  return (
                    <React.Fragment key={i}>
                      <tr>
                        <S.SpanDetailSectionHeaderTd colSpan={2}>
                          Result Set {i + 1}
                        </S.SpanDetailSectionHeaderTd>
                      </tr>
                      {result.inputs != null && (
                        <React.Fragment>
                          <tr>
                            <S.SpanDetailIOSectionHeaderTd colSpan={2}>
                              Inputs
                            </S.SpanDetailIOSectionHeaderTd>
                          </tr>
                          {Object.entries(result.inputs).map(
                            ([key, value], j) => {
                              return (
                                <DetailKeyValueRow
                                  key={j}
                                  label={key}
                                  value={value}
                                />
                              );
                            }
                          )}
                        </React.Fragment>
                      )}
                      {result.outputs != null && (
                        <React.Fragment>
                          <tr>
                            <S.SpanDetailIOSectionHeaderTd colSpan={2}>
                              Outputs
                            </S.SpanDetailIOSectionHeaderTd>
                          </tr>
                          {Object.entries(result.outputs).map(
                            ([key, value], j) => {
                              return (
                                <DetailKeyValueRow
                                  key={j}
                                  label={key}
                                  value={value}
                                />
                              );
                            }
                          )}
                        </React.Fragment>
                      )}
                    </React.Fragment>
                  );
                })}
              </>
            )}
            <tr>
              <S.SpanDetailSectionHeaderTd colSpan={2}>
                Metadata
              </S.SpanDetailSectionHeaderTd>
            </tr>
            {span.span_id != null && (
              <DetailKeyValueRow label="ID" value={span.span_id} />
            )}
            {span.span_kind != null && (
              <DetailKeyValueRow label="Kind" value={span.span_kind} />
            )}
            {span.status_code != null && (
              <DetailKeyValueRow label="Status" value={span.status_code} />
            )}
            {span.start_time_ms != null && (
              <DetailKeyValueRow
                label="Start Time"
                value={'' + new Date(span.start_time_ms)}
              />
            )}
            {span.end_time_ms != null && (
              <DetailKeyValueRow
                label="End Time"
                value={'' + new Date(span.end_time_ms)}
              />
            )}
            {span.child_spans != null && span.child_spans.length > 0 && (
              <DetailKeyValueRow
                label="Child Spans"
                value={span.child_spans.length}
              />
            )}
            {span.attributes != null &&
              Object.entries(span.attributes).map(([key, value], i) => {
                return <DetailKeyValueRow key={i} label={key} value={value} />;
              })}
          </tbody>
        </S.SpanDetailTable>
      </S.SpanDetailWrapper>
    </S.TraceDetailWrapper>
  );
};

const safeValue = (value: any) => {
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
};

const DetailKeyValueRow: React.FC<{
  label: string;
  value: any;
  style?: React.CSSProperties;
}> = props => {
  const {label, value} = props;
  const textValue = safeValue(value);
  return (
    <tr style={props.style}>
      <S.KVDetailKeyTD>{'' + label}</S.KVDetailKeyTD>
      <S.KVDetailValueTD>
        <MinimalTooltip text={textValue}>
          <S.KVDetailValueText>{textValue}</S.KVDetailValueText>
        </MinimalTooltip>
      </S.KVDetailValueTD>
    </tr>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'wb_trace_tree-traceViewer',
  canFullscreen: true,
  Component: PanelTraceTreeTrace,
  inputType,
};
