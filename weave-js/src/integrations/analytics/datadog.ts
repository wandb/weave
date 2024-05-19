// Simplified version of core/frontends/app/src/integrations.ts

import {datadogRum} from '@datadog/browser-rum';
import {once} from 'lodash';

const DATADOG_RUM_APPLICATION_ID = '79bf47c0-5363-475f-ab18-1717a0ede64f';
const DATADOG_CLIENT_TOKEN = 'pubc783f43d8359ecb9c1503e5919c8cb90';
const DATADOG_SITE = 'datadoghq.com';
const DATADOG_UI_SERVICE = 'weave-web-ui';

const doDatadogRumInit = once(() => {
  datadogRum.init({
    // TODO(np): get and append username from env
    env: window.WEAVE_CONFIG.DD_ENV,
    applicationId: DATADOG_RUM_APPLICATION_ID,
    clientToken: DATADOG_CLIENT_TOKEN,
    site: DATADOG_SITE,
    service: DATADOG_UI_SERVICE,
    trackUserInteractions: true,
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
    sessionSampleRate: 100,
    sessionReplaySampleRate: 20,
  });
});

export type DDUserInfoType = {
  username?: string;
  name?: string;
};
export function datadogSetUserInfo(userInfo: DDUserInfoType) {
  if (
    window.WEAVE_CONFIG.ANALYTICS_DISABLED ||
    window.WEAVE_CONFIG.DD_ENV === ''
  ) {
    return;
  }
  doDatadogRumInit();
  datadogRum.setUser({
    id: userInfo.username,
    name: userInfo.name,
  });
  if (userInfo.username) {
    datadogRum.startSessionReplayRecording();
  }
}
