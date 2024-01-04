import {SpanType} from '@wandb/weave/core/model/media/traceTree';
import {useNodeValue} from '@wandb/weave/react';
import React from 'react';

import * as Panel2 from '../panel';
import {
  getSpanDuration,
  getSpanIdentifier,
  getSpanKindStyle,
  MinimalTooltip,
  opSpanAsDictToLegacySpanShape,
} from './common';
import * as S from './lct.style';
import {SpanWeaveType} from './util';

const inputType = SpanWeaveType;

type PanelTraceSpanProps = Panel2.PanelProps<typeof inputType, {}>;

const PanelTraceSpan: React.FC<PanelTraceSpanProps> = props => {
  const node = opSpanAsDictToLegacySpanShape({spanDict: props.input});
  const spanValue = useNodeValue(node);
  if (spanValue.loading) {
    return <></>;
  }
  return <SpanTreeDetail span={spanValue.result as SpanType} />;
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
  if (textValue === 'null' || label.startsWith('_')) {
    return null;
  }
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

export const SpanTreeDetail: React.FC<{
  span: SpanType;
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
                if (['span_kind', 'model'].includes(key)) {
                  return null;
                }
                return (
                  <DetailKeyValueRow key={key} label={key} value={value} />
                );
              })}
          </tbody>
        </S.SpanDetailTable>
      </S.SpanDetailWrapper>
    </S.TraceDetailWrapper>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'traceSpanPanel',
  canFullscreen: true,
  Component: PanelTraceSpan,
  inputType,
};
