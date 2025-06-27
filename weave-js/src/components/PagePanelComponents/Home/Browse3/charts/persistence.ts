/*
  persistence.ts

  This file contains functions for saving and loading charts configuration from localStorage.
*/
import {v4 as uuidv4} from 'uuid';

import {ChartConfig} from './types';

export const LOCAL_STORAGE_KEY_PREFIX = 'callsChartsConfig';

function getContextualStorageKey(entity: string, project: string) {
  return `${LOCAL_STORAGE_KEY_PREFIX}_${entity}_${project}`;
}

function getDefaultChartsConfig() {
  return {
    charts: [
      {
        id: uuidv4(),
        xAxis: 'started_at',
        yAxis: 'cost',
        plotType: 'bar',
        binCount: 20,
        aggregation: 'sum',
      },
      {
        id: uuidv4(),
        xAxis: 'started_at',
        yAxis: 'latency',
        plotType: 'line',
        binCount: 20,
        aggregation: 'p95',
      },
      {
        id: uuidv4(),
        xAxis: 'prompt_tokens',
        yAxis: 'completion_tokens',
        plotType: 'scatter',
      },
    ],
    openDrawerChartId: null,
  };
}

export function loadChartsConfig(
  entity: string,
  project: string
): ChartConfig[] {
  try {
    const storageKey = getContextualStorageKey(entity, project);
    const data = localStorage.getItem(storageKey);
    if (!data) return getDefaultChartsConfig().charts as ChartConfig[];
    return JSON.parse(data).charts as ChartConfig[];
  } catch (e) {
    return getDefaultChartsConfig().charts as ChartConfig[];
  }
}

export function saveChartsConfig(config: any, entity: string, project: string) {
  try {
    const storageKey = getContextualStorageKey(entity, project);
    localStorage.setItem(storageKey, JSON.stringify({charts: config}));
  } catch (e) {
    // ignore
  }
}
