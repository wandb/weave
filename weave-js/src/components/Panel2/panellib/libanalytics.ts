declare global {
  interface Window {
    analytics?: {
      track: (name: string, data?: {[key: string]: any}) => void;
    };
  }
}

function recordWeavePanelEvent(
  action: string,
  payload?: {[key: string]: string}
) {
  const data: {[key: string]: any} = {};
  data.action = action;
  if (payload) {
    Object.assign(data, payload);
  }
  window.analytics?.track('Weave Panel Event', data);
}

export function makeEventRecorder(panelID: string) {
  return (action: string, payload?: {[key: string]: string}) => {
    return recordWeavePanelEvent(panelID + '.' + action, payload);
  };
}

export function trackWeavePanelEvent(
  panelID: string,
  payload?: {[key: string]: string}
) {
  panelID = panelID.replace(/\./g, '_').replace(/-/g, '_');
  const tableName = `wpe__${panelID}`;
  window.analytics?.track(tableName, payload);
}
