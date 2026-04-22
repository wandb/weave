import {packageVersion} from './generatedVersion';

export {packageVersion};

export function userAgent() {
  return `Weave JS Client ${packageVersion}`;
}
