import Analytics from '@segment/analytics.js-core/build/analytics';
import SegmentIntegration from '@segment/analytics.js-integration-segmentio';
import getConfig from '../config';

let isSetup = false;

export const setupAnalytics = () => {
  // If on-prem, send events to Gorilla proxy
  if (!isSetup) {
    const config = getConfig();
    isSetup = true;
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
        (window.analytics as any)?.use(SegmentIntegration);
        (window.analytics as any)?.init(integrationSettings);
      }
    }
  }
};

setupAnalytics();

export function trackPage(properties: object, options: object) {
  (window.analytics as any)?.page?.(properties, options);
}

export function trackEvent(
  eventName: string,
  eventData: Record<string, unknown>
) {
  // Taken from W&B app's Analytics.
  if (
    Array.isArray(eventData) || // Segment accepts lists but won't process them
    typeof eventData !== 'object' || // exclude the primitives
    eventData === null // typeof null => 'object' :grimace:
    // note this still leaves holes for Date / Error / any other weird "object" types
  ) {
    throw new Error('Analytics data must be a non-array object.');
  }

  (window.analytics as any)?.track?.(eventName, eventData);
}

export function trackNewBlankBoardClicked(source: string) {
  trackEvent('New blank board clicked', {source});
}

export function trackNewBoardFromTemplateClicked(
  source: string,
  template: string
) {
  trackEvent('New board from template clicked', {source, template});
}

export function trackPublishBoardClicked(source: string) {
  trackEvent('Publish board clicked', {source});
}
