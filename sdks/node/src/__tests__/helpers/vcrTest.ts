import {withCassette} from './withCassette';

export function vcrTest(
  name: string,
  fn: () => Promise<void>,
  timeout?: number
) {
  test(name, () => withCassette(fn), timeout);
}
