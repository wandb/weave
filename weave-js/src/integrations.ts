// This is a direct copy of core/frontends/app/src/integrations.ts

import {datadogLogs} from '@datadog/browser-logs';
import {datadogRum} from '@datadog/browser-rum';
import Analytics from '@segment/analytics.js-core/build/analytics';
import SegmentIntegration from '@segment/analytics.js-integration-segmentio';
import {CaptureConsole as CaptureConsoleIntegration} from '@sentry/integrations';
import * as Sentry from '@sentry/react';
import {Integrations} from '@sentry/tracing';
import {getAllCookies} from '@wandb/weave/common/util/cookie';
import {once} from 'lodash';

import config, {
  backendHost,
  datadogDebugOverride,
  envIsCloudOnprem,
  envIsLocal,
} from './config';

interface FullStoryInterface {
  getCurrentSessionURL: (addTime?: boolean) => string;
  event: (name: string, object: any) => void;
  restart: () => void;
}

// Expect these items to be in the window object.
declare global {
  interface Window {
    FS?: FullStoryInterface;
  }
}

// it gets shutdown in index.html, we restart it for logged in users in util/analytics.ts
export function restartFullstoryScript() {
  (window as any).dontShutdownFS = true;
  window.FS?.restart();
}

interface PendoInterface {
  identify: (visitor: {}, account?: {}) => any;
  initialize: (user: object) => any;
  track: (trackType: string, metadata: object) => any;
  showGuideById: (id: string) => any;
}

interface ChameleonInterface {
  identify: (userId: string | undefined, args: {}) => any;
  track: (trackType: string, metadata: object) => any;
  on: (actionType: string, functionCall: () => void) => any;
  data: any;
}

declare global {
  interface Window {
    pendo?: PendoInterface;
    chmln?: ChameleonInterface;
  }
}

declare global {
  interface Window {
    // Todo: Figure out how to hook up types from @types/prismjs

    Prism: any;
  }
}

export const Prism = window.Prism;

export function getFullStoryUrl(): string | undefined {
  return (
    window.FS &&
    window.FS.getCurrentSessionURL &&
    window.FS.getCurrentSessionURL(true)
  );
}

declare global {
  interface Window {
    DatadogEnabled?: boolean;
  }
}

// A note for future devs:
// 1) Datadog appears to wait until a couple seconds (and/or until cpu activity dies down)
//    before sending logs to the server. So if it's not logging, make sure you're waiting long enough.
//    Even though there is a delay, it will still log slow events when the user leaves the
//    navigates (including leaving the site.) In my experience "log as you're navigating away"
//    (before unload/sendBeacon) isn't a 100% guarantee, but since most navigations should be
//    staying within the w&b SPA (hopefully?) we should gather enough data.
// 2) Datadog has built in support for sampling, and won't always log if sampleRate below is < 100
// yes, this is a token that's intended to be used in web clients where users
// can access it.

let datadogInitDone = false;

const DATADOG_RUM_APPLICATION_ID = 'ddeeb29c-5e8c-4579-90be-f7c0cc91dbcd';
const DATADOG_CLIENT_TOKEN = 'pubd5ed7cb03440cfa062ac078ece38b277';
const DATADOG_SITE = 'datadoghq.com';
const DATADOG_UI_SERVICE = 'wandb-web-ui';

export const getDatadog = (
  isAdmin: boolean // when the user is admin, don't report back to DD, since it polllutes the logs.
): typeof datadogLogs | undefined => {
  // ensure we're adhering to thirdPartyAnalyticsOK
  if (
    !datadogDebugOverride() &&
    (typeof window === 'undefined' || !window.DatadogEnabled || isAdmin)
  ) {
    return;
  }
  if (!datadogInitDone) {
    if (datadogDebugOverride()) {
      console.log('Initializing DataDog - debug output enabled');
    }
    datadogLogs.init({
      clientToken: DATADOG_CLIENT_TOKEN,
      env: window.CONFIG?.ENVIRONMENT_NAME,
      site: DATADOG_SITE,
      forwardErrorsToLogs: false,
      sampleRate: datadogDebugOverride() ? 100 : 25, // only send logs for X% of _sessions_
      service: DATADOG_UI_SERVICE,
    });
    datadogInitDone = true;
  }
  return datadogLogs;
};

const doDatadogRumInit = once(() => {
  // ensure we're adhering to thirdPartyAnalyticsOK
  if (
    !datadogDebugOverride() &&
    (typeof window === 'undefined' || !window.DatadogEnabled)
  ) {
    return;
  }

  datadogRum.init({
    // TODO(np): get and append username from env
    env: window.CONFIG?.ENVIRONMENT_NAME,
    applicationId: DATADOG_RUM_APPLICATION_ID,
    clientToken: DATADOG_CLIENT_TOKEN,
    site: DATADOG_SITE,
    service: DATADOG_UI_SERVICE,
    trackInteractions: true,
    trackLongTasks: true,
    trackResources: true,
    allowedTracingUrls: [
      // local dev
      'http://api.wandb.test',
      'https://api.wandb.test',
      'https://weave.wandb.test',

      // qa
      'https://api.qa.wandb.ai',
      'https://weave.qa.wandb.ai',

      // prod
      'https://api.wandb.ai',
      'https://weave.wandb.ai',
    ].map(url => ({match: url, propagatorTypes: ['b3multi']})),
    defaultPrivacyLevel: 'mask-user-input',
    sampleRate: 100,
    sessionReplaySampleRate: 100,
    tracingSampleRate: 100,
  });
});

export function datadogSetUserInfo(userInfo: {
  username?: string;
  name?: string;
}) {
  doDatadogRumInit();
  datadogRum.setUser({
    id: userInfo.username,
    name: userInfo.name,
  });
  if (userInfo.username !== 'anonymous') {
    datadogRum.startSessionReplayRecording();
  }
}

interface ErrorParams {
  tags?: {[key: string]: string};
  extra?: {[key: string]: any};
  level?: Sentry.SeverityLevel;
  fingerprint?: string[];
}

// You must pass callsite, a string indicating what part of our code
// base captureError was called from.
export function captureError(
  err: Error | string | unknown,
  callsite: string,
  errorParams: ErrorParams = {}
) {
  const extra = {
    ...(errorParams.extra || {}),
    callsite,
    state: getStateDump(),
  };
  Sentry.withScope(scope => {
    scope.setTag('callsite', callsite);
    scope.setExtras(extra);
    if (errorParams.level) {
      scope.setLevel(errorParams.level);
    }
    Object.entries(errorParams.tags || {}).forEach(([key, value]) => {
      scope.setTag(key, value);
    });
    if (errorParams.fingerprint != null) {
      scope.setFingerprint(errorParams.fingerprint);
    }
    if (typeof err === 'string') {
      Sentry.captureMessage(err);
    } else {
      Sentry.captureException(err);
    }
  });
}

export const getStateDump = () => ({
  // eslint-disable-next-line no-restricted-globals
  localStorage: dumpStorageData(localStorage),
  // eslint-disable-next-line no-restricted-globals
  sessionStorage: dumpStorageData(sessionStorage),
  cookies: dumpCookieData(),
});

const dumpStorageData = (s: Storage) => {
  const data: {[key: string]: any} = {};
  for (let i = 0; i < s.length; i++) {
    const key = s.key(i)!;
    const val = s.getItem(key);
    try {
      data[key] = JSON.parse(val!);
    } catch {
      data[key] = val;
    }
  }
  return data;
};

const dumpCookieData = () => {
  const data: {[key: string]: any} = {};
  const cookies = getAllCookies();
  for (const [key, val] of Object.entries(cookies)) {
    try {
      data[key] = JSON.parse(val as string);
    } catch {
      data[key] = val;
    }
  }
  return data;
};

// Reload on error on dashboard pages
export function shouldReloadOnError(): boolean {
  return window.location.pathname.indexOf('/dashboards') > -1;
}

// To avoid race condition related to `window.thirdPartyAnalyticsOK`
// which was preventing Sentry from being initialized when it should,
// we simply always init Sentry, which is a no-op if the env doesn't
// contain a valid Sentry DSN
Sentry.init({
  dsn: config.SENTRY_DSN,
  environment: config.SENTRY_ENVIRONMENT,
  integrations: [
    new Integrations.BrowserTracing(),
    new CaptureConsoleIntegration({levels: ['error']}),
  ],
  tracesSampleRate: 0.1,
  release: config.GIT_TAG,
  normalizeDepth: Infinity,
  beforeSend(event, hint) {
    const error = hint && (hint.originalException as any);
    event.extra = event.extra || {};
    event.extra.fullstory =
      getFullStoryUrl() || 'current session URL API not ready';

    if (window.FS && window.FS.event) {
      window.FS.event('Application Error', {
        name: typeof error === 'string' ? error : error?.name,
        message: typeof error === 'string' ? error : error?.message,
        fileName: typeof error !== 'string' && error?.message,
        stack: typeof error !== 'string' && error?.stack,
        sentryEventId: hint?.event_id,
      });
    }

    // Check if this is a full-page error, and if so, show the report dialog
    if (
      typeof error === 'string' &&
      error.includes('Encountered ErrorBoundary')
    ) {
      Sentry.showReportDialog({eventId: event.event_id});
    }

    return event;
  },
  ignoreErrors: [
    // From RO author: "This error means that ResizeObserver was not able to deliver all observations within
    // a single animation frame. It is benign (your site will not break)."
    // https://stackoverflow.com/questions/49384120/resizeobserver-loop-limit-exceeded#comment86691361_49384120
    'ResizeObserver loop limit exceeded',
    'ResizeObserver loop completed with undelivered notifications',

    // This is MSFT Safe Link agent with poor JS compatibility
    // https://forum.sentry.io/t/unhandledrejection-non-error-promise-rejection-captured-with-value/14062/4
    // (as mentioned in that thread, confirmed the IPs via who.is)
    'Object Not Found Matching Id',

    // Displayed on every rate-limited request
    'status code 429',

    // This is an Edge Bing Instant Search bar error
    // https://stackoverflow.com/questions/69261499/what-is-instantsearchsdkjsbridgeclearhighlight
    "Can't find variable: instantSearchSDKJSBridgeClearHighlight",

    // We add a safety try/catch when accessing local storage which gets hit in environments
    // where local storage is unavailable. Leaving a console.error in the event it's helpful
    // debugging any future issue that might have a fragile dependency on its availability.
    'Storage may not be available in this environment.',
  ],
});

if ((envIsLocal || envIsCloudOnprem) && !config.DISABLE_TELEMETRY) {
  let host = backendHost();
  if (host === '') {
    host = document.location.origin;
  }
  if (host.startsWith('https://')) {
    const apiHost = host.replace('https://', '') + '/analytics';
    const integrationSettings = {
      'Segment.io': {
        apiHost,
        retryQueue: true,
      },
    };
    window.analytics = new (Analytics as any)();
    window.analytics.use(SegmentIntegration);
    window.analytics.init(integrationSettings);
  }
}
