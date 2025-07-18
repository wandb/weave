import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {FC, useMemo} from 'react';

import {
  EvaluationComparisonState,
  useEvaluationComparisonState,
} from '../CompareEvaluationsPage/ecpState';
import {MagicAnalysisBase, MagicAnalysisConfig} from './MagicAnalysisBase';

const MAGIC_EVALUATION_ANALYSIS_FEEDBACK_TYPE = 'wandb.magic_analysis';

const EMPTY_STATE_TITLE = 'Generate Evaluation Analysis';
const EMPTY_STATE_DESCRIPTION =
  'Use AI to analyze this evaluation run and generate insights about model performance, patterns, and potential improvements.';
const ANALYSIS_TITLE = 'Generated Evaluation Analysis';
const PLACEHOLDER =
  'Ask specific questions about the evaluation results, or leave empty for a comprehensive analysis...';
const REVISION_PLACEHOLDER =
  'Ask follow-up questions or leave empty to regenerate the analysis...';

const MAX_LLM_CONTEXT_LENGTH = 10000;

const MAGIC_EVALUATION_ANALYSIS_SYSTEM_PROMPT = `You are an ML evaluation analyst. Be direct, helpful, and use emojis + subtle data cards for visual clarity.
  
  RULES:
  - Only analyze provided data
  - NO questions or conversation
  - Focus on actionable fixes
  - Keep under 250 words total
  - Use data tables and cards tastefully to highlight only the most important concepts
  - For lists, always use valid markdown list syntax, never use special characters like •
  
  Format using these headers:
  
  ## Executive Summary 🎯
  
  <div style="background: #f8f9fa; border-left: 4px solid #6c757d; padding: 16px; margin: 12px 0; border-radius: 4px;">
  <table style="width: 100%; border-collapse: collapse;">
  <tr>
  <td style="padding: 6px; font-weight: 600; color: #495057;">🚀 Vibe Check</td>
  <td style="padding: 6px; color: #6c757d;">[Production ready? Ship it? Hold up?]</td>
  </tr>
  <tr>
  <td style="padding: 6px; font-weight: 600; color: #495057;">📈 Status</td>
  <td style="padding: 6px; color: #6c757d;">[Green/Yellow/Red]</td>
  </tr>
  <tr>
  <td style="padding: 6px; font-weight: 600; color: #495057;">🎯 Priority</td>
  <td style="padding: 6px; color: #6c757d;">[Critical/High/Medium/Low]</td>
  </tr>
  </table>
  </div>
  
  Main verdict in 2-3 sentences. What's the critical blocker?
  
  ## The Problem 🚨
  
  <div style="background: #fff8e1; border-left: 4px solid #ff9800; padding: 12px; margin: 12px 0; border-radius: 4px;">
  <table style="width: 100%; border-collapse: collapse;">
  <tr>
  <td style="padding: 8px; font-weight: 600; color: #e65100;"><code>metric_name</code></td>
  <td style="padding: 8px; font-weight: 600; color: #e65100;"><strong>X.XX</strong></td>
  <td style="padding: 8px; color: #e65100;"><em>specific issue description</em></td>
  </tr>
  </table>
  <br>
  💡 <strong>Pattern detected:</strong> [what the data reveals]
  </div>
  
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
  - "Who is our new marketing manager?"
  - "What's the Q4 planning deadline?"
  - "Show me the remote work policy"
  
  ## Quick Wins 🎉
  
  <div style="background: #e8f5e8; border-left: 4px solid #4caf50; padding: 12px; margin: 12px 0; border-radius: 4px;">
  <table style="width: 100%; border-collapse: collapse;">
  <tr>
  <td style="padding: 6px; font-weight: 600; color: #2e7d32;">🎯 Quick Win</td>
  <td style="padding: 6px; font-weight: 600; color: #2e7d32;">Impact</td>
  <td style="padding: 6px; font-weight: 600; color: #2e7d32;">Effort</td>
  </tr>
  <tr>
  <td style="padding: 6px; color: #2e7d32;"><strong>Change X to Y</strong></td>
  <td style="padding: 6px; color: #2e7d32;">+10% improvement</td>
  <td style="padding: 6px; color: #2e7d32;">5 min</td>
  </tr>
  <tr>
  <td style="padding: 6px; color: #2e7d32;"><strong>Add 3 examples</strong></td>
  <td style="padding: 6px; color: #2e7d32;">Catch edge cases</td>
  <td style="padding: 6px; color: #2e7d32;">15 min</td>
  </tr>
  </table>
  </div>
  
  ---
  ## Data Context 📊
  
  <div style="background: #f3f4f6; border: 1px solid #d1d5db; padding: 12px; margin: 12px 0; border-radius: 4px;">
  <pre style="margin: 0; font-size: 0.9em; color: #6b7280;">
  Examples: X of Y | Metrics: [list] | Eval: [name]
  Score distribution: [pattern] | Truncated: [yes/no]
  </pre>
  </div>
  
  **🔍 PATTERNS TO DETECT:**
  - Binary scores (all 0/1) → scorer is too strict
  - Aggregate vs individual mismatch → missing failure cases
  - Token/latency spikes → verbose model responses
  - Consistent failure patterns → prompt needs clarity
  
  Analyze the evaluation data provided in the additional context.`;

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
    metrics: {}, // Overall performance metrics
    examples: [], // Individual test cases with scores
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

/**
 * Creates additional context for the evaluation analysis.
 * This replaces the old system prompt interpolation pattern.
 */
const createEvaluationAnalysisContext = (
  evaluationState?: EvaluationComparisonState | null
): Record<string, any> => {
  if (!evaluationState) {
    return {};
  }

  return {
    evaluationContext: prepareEvaluationContextForLLM(evaluationState),
  };
};

export const MagicEvaluationAnalysisTab: FC<{
  entity: string;
  project: string;
  evaluationCallId: string;
}> = props => {
  return (
    <Tailwind style={{height: '100%', width: '100%'}}>
      <MagicEvaluationAnalysisTabInner {...props} />
    </Tailwind>
  );
};

const MagicEvaluationAnalysisTabInner: FC<{
  entity: string;
  project: string;
  evaluationCallId: string;
}> = ({entity, project, evaluationCallId}) => {
  const evaluationComparisonStateQuery = useEvaluationComparisonState(
    entity,
    project,
    [evaluationCallId]
  );

  const additionalContext = useMemo(() => {
    return createEvaluationAnalysisContext(
      evaluationComparisonStateQuery.result
    );
  }, [evaluationComparisonStateQuery.result]);

  const config: MagicAnalysisConfig = {
    feedbackType: MAGIC_EVALUATION_ANALYSIS_FEEDBACK_TYPE,
    emptyStateTitle: EMPTY_STATE_TITLE,
    emptyStateDescription: EMPTY_STATE_DESCRIPTION,
    analysisTitle: ANALYSIS_TITLE,
    magicButtonProps: {
      systemPrompt: MAGIC_EVALUATION_ANALYSIS_SYSTEM_PROMPT,
      placeholder: PLACEHOLDER,
      revisionPlaceholder: REVISION_PLACEHOLDER,
      additionalContext,
      showModelSelector: true,
      width: 450,
      textareaLines: 6,
      _dangerousExtraAttributesToLog: {
        entity,
        project,
        evaluationCallId,
        evalLink: `https://wandb.ai/${entity}/${project}/weave/calls/${evaluationCallId}`,
        feature: 'evaluation_analysis',
      },
    },
  };

  return (
    <MagicAnalysisBase
      entity={entity}
      project={project}
      callId={evaluationCallId}
      config={config}
    />
  );
};
