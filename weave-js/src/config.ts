import Analytics from '@segment/analytics.js-core/build/analytics';
import SegmentIntegration from '@segment/analytics.js-integration-segmentio';

interface Config {
  ENABLE_DEBUG_FEATURES: boolean;
  urlPrefixed(path: string): string;
  backendWeaveExecutionUrl(shadow?: boolean): string;
  backendWeaveViewerUrl(): string;
  backendWeaveOpsUrl(): string;
}

const WEAVE_BACKEND_HOST = (window as any).CONFIG?.WEAVE_BACKEND_HOST ?? '';

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

const DEFAULT_CONFIG: Config = {
  urlPrefixed: (path: string) => path,
  backendWeaveExecutionUrl,
  backendWeaveOpsUrl,
  backendWeaveViewerUrl,
  ENABLE_DEBUG_FEATURES: false,
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
