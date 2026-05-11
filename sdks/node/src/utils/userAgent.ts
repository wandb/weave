import {packageVersion} from './packageVersion';

export {packageVersion};

export function userAgent() {
  return `Weave JS Client ${packageVersion}`;
}
