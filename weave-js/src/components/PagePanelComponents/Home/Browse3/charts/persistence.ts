/**
 * This file contains functions for saving and loading charts configuration from localStorage.
 */

export const LOCAL_STORAGE_KEY_PREFIX = 'callsChartsConfig';

function getContextualStorageKey(
  entity: string,
  project: string,
  pageType: string
) {
  return `${LOCAL_STORAGE_KEY_PREFIX}_${entity}_${project}_${pageType}`;
}

function getDefaultChartsConfig() {
  // Simple ID generation for default charts
  const genId = () => Math.random().toString(36).substr(2, 9);

  return {
    charts: [
      // Bar chart showing cost
      {
        id: genId(),
        xAxis: 'started_at',
        yAxis: 'cost',
        plotType: 'bar',
        binCount: 20,
        aggregation: 'sum',
      },
      // Scatter plot showing prompt tokens against completion tokens
      {
        id: genId(),
        xAxis: 'prompt_tokens',
        yAxis: 'completion_tokens',
        plotType: 'scatter',
      },
      // Line chart showing p95 latency
      {
        id: genId(),
        xAxis: 'started_at',
        yAxis: 'latency',
        plotType: 'line',
        binCount: 20,
        aggregation: 'p95',
      },
    ],
    openDrawerChartId: null,
    hoveredGroup: null,
  };
}

export function loadChartsConfig(
  entity: string,
  project: string,
  pageType: string
) {
  try {
    const storageKey = getContextualStorageKey(entity, project, pageType);
    const data = localStorage.getItem(storageKey);
    if (!data) return getDefaultChartsConfig();
    return JSON.parse(data);
  } catch (e) {
    return getDefaultChartsConfig();
  }
}

export function saveChartsConfig(
  config: any,
  entity: string,
  project: string,
  pageType: string
) {
  try {
    const storageKey = getContextualStorageKey(entity, project, pageType);
    localStorage.setItem(storageKey, JSON.stringify(config));
  } catch (e) {
    // ignore
  }
}
