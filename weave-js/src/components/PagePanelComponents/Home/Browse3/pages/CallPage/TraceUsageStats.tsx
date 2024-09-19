import Box from '@mui/material/Box';
import {formatNumber} from '@wandb/weave/core/util/number';
import {getLLMTokenCost} from '@wandb/weave/util/llmTokenCosts';
import React from 'react';

import {LLMUsageSchema} from '../wfReactInterface/traceServerClientTypes';
import {
  CostToolTip,
  formatTokenCost,
  formatTokenCount,
  getUsageInputTokens,
  getUsageOutputTokens,
  isUsageDataKey,
  TokenAndCostMetrics,
  TokenToolTip,
  TokenTotals,
  TraceStat,
} from './cost';

export const TraceUsageStats = ({
  usage,
  latency_s,
}: {
  usage: {[key: string]: LLMUsageSchema};
  latency_s: number;
}) => {
  const {cost, tokens, costToolTip, tokenToolTip} =
    getTokensAndCostFromUsage(usage);

  const latency =
    (latency_s < 0.01 ? '<0.01' : formatNumber(latency_s, 'Number')) + 's';

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
      }}>
      <TraceStat icon="recent-clock" label={latency} />
      {usage && (
        <>
          {/* Tokens */}
          <TraceStat
            icon="database-artifacts"
            label={tokens}
            tooltip={tokenToolTip}
          />
          {/* Cost */}
          <TraceStat label={cost} tooltip={costToolTip} />
        </>
      )}
    </Box>
  );
};

export const getUsageFromCellParams = (params: {[key: string]: any}) => {
  const usage: {[key: string]: LLMUsageSchema} = {};
  for (const key in params) {
    if (key.startsWith('summary.usage')) {
      const usageKeys = key.replace('summary.usage.', '').split('.');
      const usageKey = usageKeys.pop() || '';
      if (isUsageDataKey(usageKey)) {
        const model = usageKeys.join('.');
        if (!usage[model]) {
          usage[model] = {
            requests: 0,
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
          };
        }
        usage[model][usageKey] = params[key];
      }
    }
  }
  return usage;
};

export const getTokensAndCostFromUsage = (usage: {
  [key: string]: LLMUsageSchema;
}) => {
  const metrics: TokenAndCostMetrics = {
    inputs: {
      cost: {
        total: 0,
      },
      tokens: {total: 0},
    },
    outputs: {
      cost: {total: 0},
      tokens: {total: 0},
    },
  };
  if (usage) {
    for (const model of Object.keys(usage)) {
      const inputTokens = getUsageInputTokens(usage[model]);
      const outputTokens = getUsageOutputTokens(usage[model]);
      const inputCost = getLLMTokenCost(model, 'input', inputTokens);
      const outputCost = getLLMTokenCost(model, 'output', outputTokens);

      metrics.inputs.cost[model] = inputCost;
      metrics.inputs.tokens[model] = inputTokens;
      metrics.outputs.cost[model] = outputCost;
      metrics.outputs.tokens[model] = outputTokens;

      metrics.inputs.cost.total += inputCost;
      metrics.inputs.tokens.total += inputTokens;
      metrics.outputs.cost.total += outputCost;
      metrics.outputs.tokens.total += outputTokens;
    }
  }
  const costNum = metrics.inputs.cost.total + metrics.outputs.cost.total;
  const cost = formatTokenCost(costNum);
  const tokensNum = metrics.inputs.tokens.total + metrics.outputs.tokens.total;
  const tokens = formatTokenCount(tokensNum);

  const costToolTip = <CostToolTip {...metrics} />;
  const tokenToolTip = <TokenToolTip {...metrics} />;

  return {costNum, cost, tokensNum, tokens, costToolTip, tokenToolTip};
};

export const getTokensFromCellParams = (params: {[key: string]: any}) => {
  const usage = getUsageFromCellParams(params);

  const metrics: TokenTotals = {
    inputs: {
      tokens: {total: 0},
    },
    outputs: {
      tokens: {total: 0},
    },
  };
  if (usage) {
    for (const model of Object.keys(usage)) {
      const inputTokens = getUsageInputTokens(usage[model]);
      const outputTokens = getUsageOutputTokens(usage[model]);

      metrics.inputs.tokens[model] = inputTokens;
      metrics.outputs.tokens[model] = outputTokens;

      metrics.inputs.tokens.total += inputTokens;
      metrics.outputs.tokens.total += outputTokens;
    }
  }
  const tokensNum = metrics.inputs.tokens.total + metrics.outputs.tokens.total;
  const tokens = formatTokenCount(tokensNum);

  const tokenToolTip = <TokenToolTip {...metrics} />;

  return {tokensNum, tokens, tokenToolTip};
};
