import getConfig from './config';
import Analytics from '@segment/analytics.js-core/build/analytics';
import SegmentIntegration from '@segment/analytics.js-integration-segmentio';

let is_setup = false;

export const setup_analytics = () => {
  // If on-prem, send events to Gorilla proxy
  if (!is_setup) {
    const config = getConfig();
    is_setup = true;
    const IS_ONPREM = config.ONPREM ?? false;
    const ANALYTICS_DISABLED = config.ANALYTICS_DISABLED ?? false;
    if (IS_ONPREM && !ANALYTICS_DISABLED) {
      const host = document.location.origin;
      if (host.startsWith('https://')) {
        const apiHost =
          host.replace('https://', '') +
          window.WEAVE_CONFIG.WEAVE_BACKEND_HOST +
          '/analytics';
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
  }
};
