import {parseRefMaybe} from '@wandb/weave/react';

import {CallSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';

export type ChartAxisField = {
  key: string;
  label: string;
  type: 'number' | 'string' | 'date' | 'boolean';
  units?: string;
  render?: (value: any) => string;
};

export const chartAxisFields: ChartAxisField[] = [
  {
    key: 'started_at',
    label: 'Start Time',
    type: 'date',
    render: v => new Date(v).toLocaleString(),
  },
  {
    key: 'ended_at',
    label: 'End Time',
    type: 'date',
    render: v => (v ? new Date(v).toLocaleString() : ''),
  },
  {
    key: 'latency',
    label: 'Latency',
    type: 'number',
    units: 'ms',
    render: v => `${v} ms`,
  },
  {
    key: 'exception',
    label: 'Exception',
    type: 'string',
  },
  {
    key: 'op_name',
    label: 'Operation Name',
    type: 'string',
  },
  {
    key: 'display_name',
    label: 'Display Name',
    type: 'string',
  },
  {
    key: 'cost',
    label: 'Cost',
    type: 'number',
    units: 'USD',
  },
  {
    key: 'prompt_tokens',
    label: 'Prompt Tokens',
    type: 'number',
  },
  {
    key: 'completion_tokens',
    label: 'Completion Tokens',
    type: 'number',
  },
  {
    key: 'prompt_cost',
    label: 'Prompt Cost',
    type: 'number',
    units: 'USD',
  },
  {
    key: 'completion_cost',
    label: 'Completion Cost',
    type: 'number',
    units: 'USD',
  },
];

export const xAxisFields: ChartAxisField[] = chartAxisFields.filter(
  f => f.key === 'started_at'
);
export const yAxisFields: ChartAxisField[] = chartAxisFields.filter(
  f =>
    f.key !== 'started_at' &&
    f.key !== 'display_name' &&
    f.key !== 'op_name' &&
    f.key !== 'exception'
);

export type ExtractedCallData = {
  started_at: string;
  ended_at?: string;
  latency?: number;
  exception?: string;
  op_name?: string;
  display_name?: string;
  cost?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  prompt_cost?: number;
  completion_cost?: number;
};

export function extractCallData(calls: CallSchema[]): ExtractedCallData[] {
  return calls.map(call => {
    const trace = call.traceCall;
    const started_at = trace?.started_at || '';
    const ended_at = trace?.ended_at;
    const latency = call.rawSpan.summary.latency_s;
    const costs = trace?.summary?.weave?.costs;

    let cost: number = 0.0;
    let prompt_tokens: number = 0;
    let completion_tokens: number = 0;
    let prompt_cost: number = 0.0;
    let completion_cost: number = 0.0;

    if (costs) {
      Object.entries(costs).forEach(([_, value]) => {
        prompt_tokens += value?.prompt_tokens || 0;
        completion_tokens += value?.completion_tokens || 0;
        prompt_cost += value?.prompt_tokens_total_cost || 0.0;
        completion_cost += value?.completion_tokens_total_cost || 0.0;
        cost += prompt_cost + completion_cost;
      });
    }

    return {
      started_at,
      ended_at,
      latency,
      exception: trace?.exception,
      op_name: trace?.op_name,
      display_name: trace?.display_name,
      cost,
      prompt_tokens,
      completion_tokens,
      prompt_cost,
      completion_cost,
    };
  });
}

export function getOpNameDisplay(opName?: string): string {
  if (!opName) return '';
  const parsed = parseRefMaybe(opName);
  if (
    parsed &&
    typeof parsed === 'object' &&
    'artifactName' in parsed &&
    parsed.artifactName
  ) {
    return parsed.artifactName;
  }
  // fallback: just show the string
  return opName;
}
