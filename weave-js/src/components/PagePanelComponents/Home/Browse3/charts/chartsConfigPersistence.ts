export const LOCAL_STORAGE_KEY = 'callsChartsConfig';

function genId() {
  return Math.random().toString(36).substr(2, 9);
}

function getDefaultChartsConfig() {
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

export function loadChartsConfig() {
  try {
    const data = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (!data) return getDefaultChartsConfig();
    return JSON.parse(data);
  } catch (e) {
    return getDefaultChartsConfig();
  }
}

export function saveChartsConfig(config: any) {
  try {
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(config));
  } catch (e) {
    // ignore
  }
}
