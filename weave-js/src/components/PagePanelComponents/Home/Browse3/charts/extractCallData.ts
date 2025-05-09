// Helper for extracting structured, extensible chartable data from raw call/trace objects

export type ExtractedCallData = {
  started_at?: string | number | Date;
  ended_at?: string | number | Date;
  latency?: number;
  cost?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  // Add more fields as needed for extensibility
  [key: string]: any;
};

/**
 * Extracts chartable fields from a raw call/trace object.
 * Extend this function to add more metrics as needed.
 */
export function extractCallData(raw: any): ExtractedCallData {
  // Example extraction logic; adapt field names as needed
  const started_at = raw.started_at || raw.traceCall?.started_at;
  const ended_at = raw.ended_at || raw.traceCall?.ended_at;
  const latency = ended_at ? raw.rawSpan?.summary?.latency_s : undefined;

  // Extract cost and token usage from traceCall.summary.weave.costs
  const costsDict = raw?.traceCall?.summary?.weave?.costs;
  const modelNames = costsDict ? Object.keys(costsDict) : [];
  const modelCosts = modelNames.map(name => costsDict[name]);
  let cost = 0;
  let total_tokens = 0;
  let prompt_tokens = 0;
  let completion_tokens = 0;
  let prompt_token_price = 0;
  let completion_token_price = 0;
  if (modelCosts.length > 0) {
    for (const modelCost of modelCosts) {
      prompt_tokens = modelCost?.prompt_tokens ?? 0;
      completion_tokens = modelCost?.completion_tokens ?? 0;
      total_tokens += prompt_tokens + completion_tokens;
      prompt_token_price = modelCost?.prompt_token_cost ?? 0;
      completion_token_price = modelCost?.completion_token_cost ?? 0;
      cost +=
        prompt_token_price * prompt_tokens +
        completion_token_price * completion_tokens;
    }
  }

  // Add more extraction logic as needed

  return {
    started_at,
    ended_at,
    latency,
    cost,
    total_tokens,
  };
}
