/**
 * Magic Evaluation Analysis System Prompt
 *
 * This module generates concise yet personable analysis of ML evaluation results.
 * Balances brevity with helpful context and visual clarity through strategic emoji use.
 *
 * KEY PRINCIPLES:
 *
 * 1. GOLDILOCKS BREVITY: ~250 words. Not too short, not too long, just right.
 *
 * 2. PERSONALITY WITH PURPOSE: Emojis as visual anchors (🎯 🚨 🔧 🎉 📊) make scanning easier.
 *
 * 3. VIBE CHECK: Executive summary includes production readiness "gut feel" alongside metrics.
 *
 * 4. COPY-PASTE READY: All fixes are exact text/values engineers can use immediately.
 *
 * 5. PATTERN → ACTION: Clear mapping from detected issues to specific fixes:
 *    - All scores 1.0 but aggregate 0.54 → "Add missing failure examples: [X, Y, Z]"
 *    - High token variance → "Add to prompt: 'Max 50 words for factual answers'"
 *    - Binary scoring → "Change scorer threshold from 1.0 to 0.8"
 *
 * 6. QUICK WINS: Highlights 1-2 easy improvements for immediate impact and dopamine hits.
 *
 * 7. VISUAL VARIETY: Uses rich markdown formatting for better scanning:
 *    - Callout blocks (>) for key insights and patterns
 *    - Code blocks for exact text changes
 *    - Bullet points (•) for dataset additions
 *    - Inline code for metrics and config values
 *    - Bold/italic for emphasis
 *
 * TOKEN OPTIMIZATION:
 * - Still uses aggressive simplification (14KB → 2KB)
 * - Prioritizes failure examples over successes
 * - Truncates outputs at 300 chars
 * - Pre-calculates insights like score discrepancies
 *
 * @module magicEvaluationAnalysis
 */

import {EvaluationComparisonState} from '../CompareEvaluationsPage/ecpState';

const MAX_LLM_CONTEXT_LENGTH = 10000;

/**
 * Context passed to the system prompt function.
 * Can be extended with additional context like user preferences or historical data.
 */
type EvaluationAnalysisContext = {
  evaluationState?: EvaluationComparisonState | null;
};
export const SYSTEM_PROMPT_FN = (
  context: EvaluationAnalysisContext
) => `You are an ML evaluation analyst. Be direct, helpful, and use emojis + markdown for visual clarity.

RULES:
- Only analyze provided data
- NO questions or conversation
- Focus on actionable fixes
- Keep under 250 words total
- Use varied markdown elements for visual hierarchy

Format using these headers:

## Executive Summary 🎯
> **Vibe Check:** [Production ready? Ship it? Hold up?]

Main verdict in 2-3 sentences. What's the critical blocker?

## The Problem 🚨
\`metric_name: X.XX\` ← *specific issue description*

> 💡 **Pattern detected:** [what the data reveals]

## Fix It Now 🔧

### Prompt Changes
\`\`\`
Add: "Always search first for: names, dates, procedures"
Replace: "[old text]" → "[new text]"
\`\`\`

### Config Tweaks
- **Temperature:** \`0.1\` for search decisions
- **Max tokens:** \`150\` to reduce verbosity
- **Threshold:** \`0.8 → 0.6\` for scorer

### Dataset Additions
• "Who is our new marketing manager?"  
• "What's the Q4 planning deadline?"  
• "Show me the remote work policy"

## Quick Wins 🎉
1. **Easy fix:** Change X to Y for instant +10% improvement
2. **Low-hanging fruit:** Add these 3 examples to catch edge cases

---
## Data Context 📊
\`\`\`
Examples: X of Y | Metrics: [list] | Eval: [name]
Score distribution: [pattern] | Truncated: [yes/no]
\`\`\`

PATTERNS TO DETECT:
- Binary scores (all 0/1) → scorer is too strict
- Aggregate vs individual mismatch → missing failure cases
- Token/latency spikes → verbose model responses
- Consistent failure patterns → prompt needs clarity

<evaluation_context>
${
  context.evaluationState
    ? prepareEvaluationContextForLLM(context.evaluationState)
    : ''
}
</evaluation_context>
`;

/**
 * Prepares evaluation data for LLM consumption with token limit handling.
 * Adds truncation metadata if the context exceeds MAX_LLM_CONTEXT_LENGTH.
 */
const prepareEvaluationContextForLLM = (results: EvaluationComparisonState) => {
  const simplifiedResults = simplifyEvaluationResults(results);
  let llmContext = JSON.stringify(simplifiedResults);

  // If we need to truncate, add a flag to the data first
  if (llmContext.length > MAX_LLM_CONTEXT_LENGTH) {
    simplifiedResults._truncated = true;
    simplifiedResults._original_length = llmContext.length;
    llmContext = JSON.stringify(simplifiedResults);

    // Still truncate if needed
    if (llmContext.length > MAX_LLM_CONTEXT_LENGTH) {
      return llmContext.slice(0, MAX_LLM_CONTEXT_LENGTH) + '...<TRUNCATED>...';
    }
  }

  return llmContext;
};

/**
 * Simplifies evaluation results for LLM analysis by removing redundancy and calculating insights.
 * Reduces ~14KB of nested data to ~2KB of actionable information.
 */
const simplifyEvaluationResults = (results: EvaluationComparisonState) => {
  const simplified: any = {
    metrics: {},      // Overall performance metrics
    examples: [],     // Individual test cases with scores
  };

  let totalRows = 0;

  // Extract summary metrics from the first evaluation
  const firstEvalId = Object.keys(results.summary?.evaluationCalls || {})[0];
  if (firstEvalId && results.summary?.evaluationCalls[firstEvalId]) {
    const evalCall = results.summary.evaluationCalls[firstEvalId];
    simplified.evalName = evalCall.name;

    // Flatten summary metrics with shorter keys
    Object.entries(evalCall.summaryMetrics || {}).forEach(([key, metric]) => {
      // Shorten scorer keys and extract just the value
      const shortKey = key.includes('AdjudicationScorer')
        ? 'score'
        : key.includes('Latency')
        ? 'latency_s'
        : key.includes('Total Tokens')
        ? 'total_tokens'
        : key;
      simplified.metrics[shortKey] = metric.value;
    });
  }

  // Extract individual examples with only essential data
  if (results.loadableComparisonResults?.result?.resultRows) {
    const rows = results.loadableComparisonResults.result.resultRows;
    totalRows = Object.keys(rows).length;

    Object.entries(rows).forEach(([rowId, rowData]) => {
      const evalData = rowData.evaluations[firstEvalId];
      if (!evalData) return;

      const predictData = Object.values(evalData.predictAndScores || {})[0];
      if (!predictData) return;

      const example: any = {
        // Extract actual question/input from the raw data
        input:
          predictData._rawPredictTraceData?.inputs?.qText || 'Unknown input',
        output: predictData._rawPredictTraceData?.output || '',
        scores: {},
      };

      // Simplify score metrics
      Object.entries(predictData.scoreMetrics || {}).forEach(
        ([key, metric]) => {
          const shortKey = key.includes('score')
            ? 'score'
            : key.includes('Latency')
            ? 'latency_s'
            : key.includes('Total Tokens')
            ? 'tokens'
            : key;
          example.scores[shortKey] = metric.value;
        }
      );

      // Only add if we have meaningful data
      if (example.input !== 'Unknown input') {
        simplified.examples.push(example);
      }
    });
  }

  // Extract actual question text from refs if needed
  simplified.examples = simplified.examples.map((ex: any) => {
    // Handle weave ref format for inputs
    if (typeof ex.input === 'string' && ex.input.startsWith('weave://')) {
      // Extract question from the trace data output instead
      const match = ex.output.match(/^(.*?)\?/);
      if (match) {
        ex.input = match[0];
      }
    }

    // Truncate very long outputs to save tokens
    if (ex.output && ex.output.length > 300) {
      ex.output = ex.output.substring(0, 300) + '...';
    }

    return ex;
  });

  // Add dataset info if available
  const datasetRef = Object.keys(results.summary?.evaluations || {})[0];
  if (datasetRef) {
    const datasetName = datasetRef.split('/').pop()?.split(':')[0] || 'unknown';
    simplified.dataset = datasetName;
  }

  // Add model info (simplified)
  const modelRef = Object.keys(results.summary?.models || {})[0];
  if (modelRef && results.summary?.models[modelRef]) {
    const modelName = modelRef.split('/').pop()?.split(':')[0] || 'unknown';
    simplified.model = modelName;
  }

  // Calculate derived insights that might not be obvious
  if (simplified.examples.length > 0) {
    const avgLatency =
      simplified.examples.reduce(
        (sum: number, ex: any) => sum + (ex.scores.latency_s || 0),
        0
      ) / simplified.examples.length;
    const avgTokens =
      simplified.examples.reduce(
        (sum: number, ex: any) => sum + (ex.scores.tokens || 0),
        0
      ) / simplified.examples.length;

    simplified.insights = {
      example_count: simplified.examples.length,
      total_rows: totalRows,
      avg_latency_s: parseFloat(avgLatency.toFixed(3)),
      avg_tokens_per_example: Math.round(avgTokens),
      // Flag potential scorer issues
      score_discrepancy:
        simplified.metrics.score !== undefined &&
        simplified.examples.every((ex: any) => ex.scores.score === 1) &&
        simplified.metrics.score < 1,
    };
  }

  return simplified;
};
