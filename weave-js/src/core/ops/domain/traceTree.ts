import * as TypeHelpers from '../../model/helpers';
import {SpanType} from '../../model/media/traceTree';
import * as OpKinds from '../opKinds';

const getFirstError = (span: SpanType): string | null => {
  if (span.status_code === 'ERROR') {
    return span.status_message ?? '';
  }
  for (const child of span.child_spans ?? []) {
    const error = getFirstError(child);
    if (error != null) {
      return error;
    }
  }
  return null;
};

const getSpanRepr = (span: SpanType): string => {
  const basicName = span.name ?? span.span_kind ?? 'Unknown';
  const innerCalls: string[] = [];
  for (const child of span.child_spans ?? []) {
    innerCalls.push(getSpanRepr(child));
  }
  if (innerCalls.length === 0) {
    return basicName;
  }
  return `${basicName}(${innerCalls.join(', ')})`;
};

const getSpanInputAsMarkdownString = (span: SpanType): string => {
  return (span.results ?? [])
    .map((result, i) => {
      return Object.entries(result.inputs ?? {})
        .map(([eKey, eValue], j) => `**${i}.${eKey}:** ${eValue}`)
        .join('\n\n');
    })
    .join('\n\n');
};

const getSpanOutputAsMarkdownString = (span: SpanType): string => {
  return (span.results ?? [])
    .map((result, i) => {
      return Object.entries(result.outputs ?? {})
        .map(([eKey, eValue], j) => `**${i}.${eKey}:** ${eValue}`)
        .join('\n\n');
    })
    .join('\n\n');
};

export const opWBTraceTreeStartTime = OpKinds.makeTaggingStandardOp({
  name: 'wb_trace_tree-startTime',
  argTypes: {
    trace_tree: {type: 'wb_trace_tree' as const},
  },
  hidden: true,
  returnType: inputTypes => TypeHelpers.maybe('number'),
  resolver: ({trace_tree}) => {
    try {
      const rootSpan = JSON.parse(trace_tree.root_span_dumps) as SpanType;
      return rootSpan.start_time_ms;
    } catch (e) {
      console.error(e);
      return null;
    }
  },
});

export const opWBTraceTreeSummary = OpKinds.makeTaggingStandardOp({
  name: 'wb_trace_tree-traceSummaryDict',
  argTypes: {
    trace_tree: {type: 'wb_trace_tree' as const},
  },
  hidden: true,
  returnType: inputTypes =>
    TypeHelpers.typedDict({
      isSuccess: TypeHelpers.maybe('boolean'),
      startTime: TypeHelpers.maybe('number'),
      formattedInput: 'string',
      formattedOutput: 'string',
      formattedChain: 'string',
      error: TypeHelpers.maybe('string'),
      modelHash: TypeHelpers.maybe('string'),
    }),
  resolver: ({trace_tree}) => {
    const {root_span_dumps, model_hash} = trace_tree;
    let rootSpan: SpanType = {};
    try {
      rootSpan = JSON.parse(root_span_dumps) as SpanType;
    } catch (e) {
      console.error(e);
    }
    return {
      isSuccess:
        rootSpan.status_code == null || rootSpan.status_code === 'SUCCESS',
      startTime: rootSpan.start_time_ms,
      formattedInput: getSpanInputAsMarkdownString(rootSpan),
      formattedOutput: getSpanOutputAsMarkdownString(rootSpan),
      formattedChain: getSpanRepr(rootSpan),
      error: getFirstError(rootSpan),
      modelHash: model_hash,
    };
  },
});
