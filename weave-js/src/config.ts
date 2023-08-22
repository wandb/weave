
import Analytics from '@segment/analytics.js-core/build/analytics';
import SegmentIntegration from '@segment/analytics.js-integration-segmentio';


declare global {
  interface Window {
    WEAVE_CONFIG: {
      PREFIX: string;
      ANALYTICS_DISABLED: boolean;
      WEAVE_BACKEND_HOST: string;
    };
  }
}
// These get populated via /__frontend/env.js and are defined in weave_server.py
if (!window.WEAVE_CONFIG) {
  console.warn('Unable to get configuration from server, using defaults');
  window.WEAVE_CONFIG = {
    PREFIX: '',
    ANALYTICS_DISABLED: false,
    WEAVE_BACKEND_HOST: '/__weave',
  };
}

interface Config {
  ENABLE_DEBUG_FEATURES: boolean;
  ANALYTICS_DISABLED: boolean;
  PREFIX: string;
  urlPrefixed(path: string): string;
  backendWeaveExecutionUrl(shadow?: boolean): string;
  backendWeaveViewerUrl(): string;
  backendWeaveOpsUrl(): string;
}

const WEAVE_BACKEND_HOST = window.WEAVE_CONFIG.WEAVE_BACKEND_HOST;

const backendWeaveExecutionUrl = (shadow: boolean = false) => {
  if (shadow) {
    return WEAVE_BACKEND_HOST + '/shadow_execute';
  }
  return WEAVE_BACKEND_HOST + '/execute';
};

const backendWeaveOpsUrl = () => {
  return WEAVE_BACKEND_HOST + '/ops';
};

const backendWeaveViewerUrl = () => {
  return WEAVE_BACKEND_HOST + '/wb_viewer';
};

export const urlPrefixed = (path: string, host: boolean = false) => {
  let url = new URL(window.location.origin + window.WEAVE_CONFIG.PREFIX);
  url = new URL(url.href.replace(/\/$/, '') + path);
  if (!host) {
    return url.pathname + url.search;
  }
  return url.href;
};

const DEFAULT_CONFIG: Config = {
  urlPrefixed,
  backendWeaveExecutionUrl,
  backendWeaveOpsUrl,
  backendWeaveViewerUrl,
  PREFIX: window.WEAVE_CONFIG.PREFIX,
  ENABLE_DEBUG_FEATURES: false,
  ANALYTICS_DISABLED: window.WEAVE_CONFIG.ANALYTICS_DISABLED,
} as const;

let config = {...DEFAULT_CONFIG};

export const setConfig = (newConfig: Partial<Config>) => {
  config = {...config, ...newConfig};
};

export default function getConfig() {
  return config;
}

// If on-prem, send events to Gorilla proxy
const IS_ONPREM = (window as any).CONFIG?.ONPREM ?? false;
const ANALYTICS_DISABLED = (window as any).CONFIG?.ANALYTICS_DISABLED ?? false;
if (IS_ONPREM && !ANALYTICS_DISABLED) {
  const host = document.location.origin;
  if (host.startsWith('https://')) {
    const apiHost =
      host.replace('https://', '') + WEAVE_BACKEND_HOST + '/analytics';
    const integrationSettings = {
      'Segment.io': {
        apiHost,
        retryQueue: true,
      },
    };
    window.analytics = new (Analytics as any)();
    (window.analytics as any).use(SegmentIntegration);
    (window.analytics as any).init(integrationSettings);
  }
}
