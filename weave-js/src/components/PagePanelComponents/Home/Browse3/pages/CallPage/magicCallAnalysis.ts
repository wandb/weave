/**
 * Magic Call Analysis System Prompt
 *
 * This module generates insightful analysis of Weave call data.
 * Provides flexible analysis for any type of call with helpful insights and patterns.
 *
 * KEY PRINCIPLES:
 *
 * 1. ADAPTIVE ANALYSIS: Works with any call type - ML models, workflows, or custom functions
 *
 * 2. PATTERN RECOGNITION: Identifies performance bottlenecks, error patterns, and optimization opportunities
 *
 * 3. ACTIONABLE INSIGHTS: Focuses on practical improvements and debugging guidance
 *
 * 4. VISUAL CLARITY: Uses markdown and emojis for better readability
 *
 * @module magicCallAnalysis
 */

import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

/**
 * Context passed to the system prompt function.
 */
type CallAnalysisContext = {
  call?: CallSchema | null;
};

export const SYSTEM_PROMPT_FN = (
  context: CallAnalysisContext
) => `You are a Weave call analyst. Analyze the provided call data and provide insights about performance, patterns, and potential improvements.

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

<call_context>
${context.call ? prepareCallContextForLLM(context.call) : ''}
</call_context>
`;

/**
 * Prepares call data for LLM consumption, extracting relevant information.
 */
const prepareCallContextForLLM = (call: CallSchema) => {
  const simplified: any = {
    callId: call.callId,
    spanName: call.spanName,
    status: call.traceCall?.exception ? 'failed' : 'success',
    startedAt: call.startedAt,
    endedAt: call.endedAt,
  };

  // Calculate duration if both timestamps exist
  if (call.startedAt && call.endedAt) {
    const duration =
      new Date(call.endedAt).getTime() - new Date(call.startedAt).getTime();
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
