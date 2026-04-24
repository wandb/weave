import {packageVersion} from './packageVersion.js';

export {packageVersion};

export function userAgent() {
  return `Weave JS Client ${packageVersion}`;
}
