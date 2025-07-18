import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {FC, useMemo} from 'react';

import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {MagicAnalysisBase, MagicAnalysisConfig} from './MagicAnalysisBase';

const MAGIC_CALL_ANALYSIS_FEEDBACK_TYPE = 'wandb.magic_call_analysis';

const EMPTY_STATE_TITLE = 'Generate Call Analysis';
const EMPTY_STATE_DESCRIPTION =
  'Use AI to analyze this call and generate insights about performance, patterns, and potential improvements.';
const ANALYSIS_TITLE = 'Generated Call Analysis';
const PLACEHOLDER =
  'Ask specific questions about the call, or leave empty for a comprehensive analysis...';
const REVISION_PLACEHOLDER =
  'Ask follow-up questions or leave empty to regenerate the analysis...';

const MAGIC_CALL_ANALYSIS_SYSTEM_PROMPT = `You are a Weave call analyst. Analyze the provided call data and provide insights about performance, patterns, and potential improvements.

RULES:
- Only analyze provided data
- NO questions or conversation
- Focus on actionable insights
- Keep under 300 words total
- Use varied markdown elements for visual hierarchy
- For lists, always use valid markdown list syntax

Format using these headers:

## Overview 🔍
Brief summary of what this call does and its current state.

## Key Insights 📊
What patterns or interesting behaviors emerge from the data?

## Performance Analysis ⚡
Latency, token usage, resource consumption patterns.

## Recommendations 🎯
Specific improvements or optimizations to consider.

## Next Steps 🚀
Concrete actions to take based on this analysis.

---
## Call Details 📋
\`\`\`
Type: [call type] | Status: [status]
Duration: [time] | Tokens: [if applicable]
\`\`\`

PATTERNS TO DETECT:
- High latency or token usage
- Error patterns or failed calls
- Repeated operations that could be optimized
- Resource inefficiencies
- Unusual input/output patterns

Analyze the call data provided in the additional context.`;

/**
 * Prepares call data for LLM consumption, extracting relevant information.
 */
const prepareCallContextForLLM = (call: CallSchema) => {
  const simplified: any = {
    callId: call.callId,
    spanName: call.spanName,
    status: call.traceCall?.exception ? 'failed' : 'success',
    startedAt: call.rawSpan.start_time_ms,
    endedAt: call.rawSpan.end_time_ms,
  };

  // Calculate duration if both timestamps exist
  if (call.rawSpan.start_time_ms && call.rawSpan.end_time_ms) {
    const duration = call.rawSpan.end_time_ms - call.rawSpan.start_time_ms;
    simplified.durationMs = duration;
    simplified.durationSeconds = (duration / 1000).toFixed(2);
  }

  // Extract trace call data if available
  if (call.traceCall) {
    simplified.inputs = call.traceCall.inputs;
    simplified.output = call.traceCall.output;
    simplified.exception = call.traceCall.exception;

    // Extract summary metrics if available
    if (call.traceCall.summary) {
      simplified.summary = call.traceCall.summary;
    }

    // Extract attributes for additional context
    if (call.traceCall.attributes) {
      simplified.attributes = call.traceCall.attributes;
    }
  } else {
    // Fallback to raw span data
    simplified.inputs = call.rawSpan.inputs;
    simplified.output = call.rawSpan.output;
    simplified.exception = call.rawSpan.exception;
    simplified.summary = call.rawSpan.summary;
    simplified.attributes = call.rawSpan.attributes;
  }

  // Add op version info if available
  if (call.opVersionRef) {
    simplified.opVersion = call.opVersionRef;
  }

  // Truncate very long outputs to save tokens
  if (simplified.output && JSON.stringify(simplified.output).length > 1000) {
    simplified.output =
      JSON.stringify(simplified.output).substring(0, 1000) + '...<truncated>';
  }

  return JSON.stringify(simplified, null, 2);
};

/**
 * Creates additional context for the call analysis.
 * This replaces the old system prompt interpolation pattern.
 */
const createCallAnalysisContext = (
  call?: CallSchema | null
): Record<string, any> => {
  if (!call) {
    return {};
  }

  return {
    callContext: prepareCallContextForLLM(call),
  };
};

export const MagicCallAnalysisTab: FC<{
  entity: string;
  project: string;
  callId: string;
}> = props => {
  return (
    <Tailwind style={{height: '100%', width: '100%'}}>
      <MagicCallAnalysisTabInner {...props} />
    </Tailwind>
  );
};

const MagicCallAnalysisTabInner: FC<{
  entity: string;
  project: string;
  callId: string;
}> = ({entity, project, callId}) => {
  const {useCall} = useWFHooks();

  // Fetch the call data
  const callQuery = useCall({
    key: {
      entity,
      project,
      callId,
    },
    includeCosts: true,
    includeTotalStorageSize: true,
  });

  const call = callQuery.result;

  const additionalContext = useMemo(() => {
    return createCallAnalysisContext(call as CallSchema | null);
  }, [call]);

  const config: MagicAnalysisConfig = {
    feedbackType: MAGIC_CALL_ANALYSIS_FEEDBACK_TYPE,
    emptyStateTitle: EMPTY_STATE_TITLE,
    emptyStateDescription: EMPTY_STATE_DESCRIPTION,
    analysisTitle: ANALYSIS_TITLE,
    magicButtonProps: {
      systemPrompt: MAGIC_CALL_ANALYSIS_SYSTEM_PROMPT,
      placeholder: PLACEHOLDER,
      revisionPlaceholder: REVISION_PLACEHOLDER,
      additionalContext,
      showModelSelector: true,
      width: 450,
      textareaLines: 6,
      _dangerousExtraAttributesToLog: {
        entity,
        project,
        callId,
        callLink: `https://wandb.ai/${entity}/${project}/weave/calls/${callId}`,
        feature: 'call_analysis',
      },
    },
  };

  return (
    <MagicAnalysisBase
      entity={entity}
      project={project}
      callId={callId}
      config={config}
    />
  );
};
