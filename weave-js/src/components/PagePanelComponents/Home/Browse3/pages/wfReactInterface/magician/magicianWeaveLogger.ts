// THIS IS A MEGA HACKY FILE TO LOG TO WEAVE _ NO PROD!

import {DirectTraceServerClient} from '../traceServerDirectClient';

/** Direct trace server client for logging to Weave */
const hackweekClient = new DirectTraceServerClient(
  'https://trace.wandb.ai',
  // Security Note: An API key once once checked in here, but was immediately removed and rotated.
);

/** Project ID for logging magic calls */
const projectId = 'PROJECT_ID';

/**
 * Logs a magic call to Weave for debugging and analysis.
 *
 * This is a temporary logging solution for development purposes.
 * Logs both the start and end of magic operations with inputs, outputs, and attributes.
 *
 * @param op_name The name of the operation being logged
 * @param inputs The input parameters for the operation
 * @param outputs The output/result of the operation
 * @param attributes Optional additional attributes to log
 *
 * @example
 * ```typescript
 * await dangerouslyLogCallToWeave(
 *   'chatCompletionStream',
 *   { messages: 'Hello world', temperature: 0.7 },
 *   'Hello! How can I help you today?',
 *   { userId: '123', feature: 'magic_tooltip' }
 * );
 * ```
 */
export const dangerouslyLogCallToWeave = async (
  op_name: string,
  inputs: Record<string, any>,
  outputs: unknown,
  attributes?: Record<string, any>
) => {
  const res = await hackweekClient.callStart({
    start: {
      op_name,
      inputs,
      project_id: projectId,
      started_at: new Date().toISOString(),
      attributes: attributes || {},
    },
  });
  await hackweekClient.callEnd({
    end: {
      id: res.id,
      project_id: projectId,
      ended_at: new Date().toISOString(),
      output: outputs,
      summary: {},
    },
  });
};
