export const LOCAL_STORAGE_KEY = 'callsChartsConfig';

export function loadChartsConfig() {
  try {
    const data = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (!data) return undefined;
    return JSON.parse(data);
  } catch (e) {
    return undefined;
  }
}

export function saveChartsConfig(config: any) {
  try {
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(config));
  } catch (e) {
    // ignore
  }
}
