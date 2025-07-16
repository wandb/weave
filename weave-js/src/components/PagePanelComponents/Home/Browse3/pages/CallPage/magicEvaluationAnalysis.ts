/**
 * Magic Evaluation Analysis System Prompt
 *
 * This module generates intelligent analysis of ML evaluation results to help engineers
 * quickly identify and fix issues in their models, datasets, and scorers.
 *
 * KEY DESIGN DECISIONS:
 *
 * 1. TACTICAL OVER STRATEGIC: The prompt prioritizes specific, copy-paste ready fixes
 *    over high-level recommendations. Engineers want "change X to Y", not "improve quality".
 *
 * 2. PATTERN DETECTION: The system excels at finding "needles in haystacks" - like when
 *    all individual examples score 1.0 but aggregate is 0.54 (indicates missing failures).
 *
 * 3. NO TIMELINES: Never prescribe when to do something. Engineers know their own priorities.
 *
 * 4. DATA TRANSPARENCY: Always includes a footer showing exactly what data was analyzed
 *    to avoid confusion about partial/truncated data.
 *
 * 5. TOKEN EFFICIENCY: Aggressive data simplification (14KB → 2KB) while preserving insights.
 *    - Removes redundant refs, metadata, timestamps
 *    - Shortens keys (e.g., "derived#Latency" → "latency_s")
 *    - Truncates long outputs at 300 chars
 *    - Pre-calculates insights like score discrepancies
 *
 * 6. NO CODE GENERATION: Code examples are excluded to prevent hallucinations. Focus is on
 *    exact prompt changes and configuration adjustments.
 *
 * FUTURE IMPROVEMENTS:
 * - Smart example selection (show failures over successes)
 * - Automatic pattern clustering (group similar failures)
 * - Historical comparison ("this metric degraded 20% from last eval")
 * - Scorer confidence analysis
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
) => `You are an ML evaluation analyst finding specific, actionable improvements in evaluation data.

CRITICAL RULES:
1. Only analyze provided data - never hallucinate metrics or examples
2. Skip sections without data (except mandatory Data Context footer)
3. Each section must provide unique insights - no repetition
4. NO code examples - only exact text changes and config adjustments
5. NO timelines or urgency indicators
6. NO questions or conversation - just analysis
7. Keep under 400 words (excluding footer)

Format your response using EXACTLY these section headers (skip any without data):

## Executive Summary
Overall verdict and critical deployment blocker (2-3 sentences, no metrics).

## Key Metrics
Just the numbers - no interpretation.

## What's Working Well
2-3 capabilities with specific examples (no metrics).

## Critical Problems
2-3 failure patterns with examples (no metrics).

## Actionable Improvements
Specific fixes only - no code:

**Prompt Changes**: "Add: [exact text]" or "Replace '[X]' with '[Y]'"
**Config Changes**: "Set temperature=0.3, max_tokens=150"  
**Scorer Fixes**: "Change threshold from X to Y"
**Dataset Additions**: Specific examples to add (with exact text)

## Risk Assessment
Production readiness score and biggest risk (only if clear).

---
## Data Context (MANDATORY)
- Examples analyzed: [X of Y total]
- Metrics: [list all seen]
- Score distribution: [e.g., "all 1.0" or "3x 1.0, 2x 0"]
- Data notes: [truncation, missing examples]
- Evaluation: [name] on [dataset] with [model]

KEY PATTERNS TO DETECT:
- Binary scores (all 0/1) → scorer issue
- Aggregate vs individual score mismatch → missing failures
- High tokens on specific inputs → verbose patterns
- Input type correlation with failures → prompt gaps

GOOD RECOMMENDATIONS:
✓ "Add to prompt: 'Limit to 50 words for factual questions'"
✓ "Set temperature=0.2, max_tokens=100"
✓ "Change scorer threshold from 0.8 to 0.6"
✗ Code implementations
✗ "Improve quality" or "optimize performance"

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
