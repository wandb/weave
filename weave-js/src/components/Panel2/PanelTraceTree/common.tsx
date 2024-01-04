import {
  constNumber,
  constString,
  Node,
  opArray,
  opDict,
  opMerge,
  opNoneCoalesce,
  opNumberMult,
  opPick,
} from '@wandb/weave/core';
import {SpanKindType, SpanType} from '@wandb/weave/core/model/media/traceTree';
import React, {PropsWithChildren, ReactNode} from 'react';

import {AgentSVG, ChainSVG, LLMSVG, ToolSVG} from '../Icons';
import {TooltipTrigger} from '../Tooltip';

export const chainColor = '#F59B1414';
export const chainTextColor = '#C77905';
export const toolColor = '#9CC74818';
export const toolTextColor = '#669432';
export const agentColor = '#0096AD14';
export const agentTextColor = '#0096AD';
export const llmColor = '#CD5BF016';
export const llmTextColor = '#9E36C2';
export const promptColor = '#9278EB18';
export const promptTextColor = '#775CD1';

export const MinimalTooltip: React.FC<
  PropsWithChildren<{text: string; lengthLimit?: number}>
> = ({children, text, lengthLimit}) => {
  const limit = lengthLimit ?? 100;
  if (text.length < limit) {
    return <>{children}</>;
  }
  return (
    <TooltipTrigger copyableContent={text} content={<pre>{text}</pre>}>
      {children}
    </TooltipTrigger>
  );
};

type SpanKindStyle = {
  color: string;
  textColor: string;
  label: string;
  icon: ReactNode;
};

export function getSpanKindStyle(kind?: SpanKindType): SpanKindStyle {
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

export const getSpanIdentifier = (span: SpanType) => {
  return span.name ?? span._name ?? span.span_kind ?? 'Unknown';
};

export const getSpanDuration = (span: SpanType) => {
  if (span.end_time_ms && span.start_time_ms) {
    return span.end_time_ms - span.start_time_ms;
  }
  return null;
};

export const opSpanAsDictToLegacySpanShape = ({spanDict}: {spanDict: Node}) => {
  // Needs to map SpanWeaveType to SpanType
  return opDict({
    name: opPick({obj: spanDict, key: constString('name')}),
    start_time_ms: opNumberMult({
      lhs: opPick({
        obj: spanDict,
        key: constString('start_time_s'),
      }),
      rhs: constNumber(1000),
    }),
    end_time_ms: opNumberMult({
      lhs: opPick({
        obj: spanDict,
        key: constString('end_time_s'),
      }),
      rhs: constNumber(1000),
    }),
    trace_id: opPick({obj: spanDict, key: constString('trace_id')}),
    span_id: opPick({obj: spanDict, key: constString('span_id')}),
    parent_id: opPick({obj: spanDict, key: constString('parent_id')}),
    status_code: opPick({obj: spanDict, key: constString('status_code')}),
    status_message: opPick({obj: spanDict, key: constString('exception')}),
    attributes: opMerge({
      lhs: opNoneCoalesce({
        lhs: opPick({obj: spanDict, key: constString('attributes')}),
        rhs: opDict({} as any),
      }) as any,
      rhs: opNoneCoalesce({
        lhs: opPick({obj: spanDict, key: constString('summary')}),
        rhs: opDict({} as any),
      }) as any,
    }),
    span_kind: opPick({
      obj: spanDict,
      key: constString('attributes.span_kind'),
    }),
    results: opArray({
      a: opDict({
        inputs: opPick({obj: spanDict, key: constString('inputs')}),
        outputs: opPick({obj: spanDict, key: constString('output')}),
      } as any),
    } as any),
  } as any);
};
