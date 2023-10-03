// Direct copy of the Datadog integration from the Weights & Biases codebase
// Minimal implementation of RUM logging

import {datadogRum} from '@datadog/browser-rum';
import {once} from 'lodash';

declare global {
  interface Window {
    DatadogEnabled?: boolean;
  }
}

const DATADOG_RUM_APPLICATION_ID = 'ddeeb29c-5e8c-4579-90be-f7c0cc91dbcd';
const DATADOG_SITE = 'datadoghq.com';
const DATADOG_UI_SERVICE = 'wandb-weave-ui';

const doDatadogRumInit = once(() => {
  // ensure we're adhering to thirdPartyAnalyticsOK
  if (typeof window === 'undefined') {
    return;
  }

  const clientToken = window.WEAVE_CONFIG?.DD_CLIENT_TOKEN;
  const env = window.WEAVE_CONFIG?.DD_ENV;

  if (!clientToken || !env) {
    return;
  }

  datadogRum.init({
    // TODO(np): get and append username from env
    env,
    applicationId: DATADOG_RUM_APPLICATION_ID,
    clientToken,
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
