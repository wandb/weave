/* tslint:disable */

/**
 * This test should only run when testing against the weave python backend. It iterates
 * through all the known TS Ops and evaluates the python compatibility of each one.
 */

import {typeToString} from './language/js/print';
import {OpStore} from './opStore';
import {
  CompatResult,
  CompatState,
  compatToString,
  evaluateOpInputCompatibility,
  evaluateOpOutputCompatibility,
} from './opStore/mixedOpStore';
import {loadRemoteOpStore} from './opStore/remoteOpStore';
import {StaticOpStore} from './opStore/static';
import {getTestRemoteURL} from './testUtil';

const remoteOpStores: {[url: string]: OpStore} = {};

const getRemoteOpStore = async (remoteURL: string) => {
  if (remoteOpStores[remoteURL] == null) {
    const {remoteOpStore} = await loadRemoteOpStore(remoteURL + '/ops');
    remoteOpStores[remoteURL] = remoteOpStore;
  }
  return remoteOpStores[remoteURL];
};

const processResult = (result: CompatResult) => {
  let res = `${compatToString(result.state)} due to: `;
  res += result.details
    .filter(d => typeof d === 'string' || d.message !== 'Exact')
    .map(d =>
      typeof d === 'string'
        ? d
        : d.message +
          (d.key != null ? ' for param `' + d.key + '`' : 'for output type') +
          (d.message.includes('function node')
            ? ''
            : ' (TS = ' +
              typeToString(d.localType, false).replace(/\s/g, '') +
              ' vs PY = ' +
              typeToString(d.serverType, false).replace(/\s/g, '') +
              ')')
    )
    .join(', ');
  return res;
};

describe('op compatibility', () => {
  const remoteURL: string | undefined = getTestRemoteURL();
  if (remoteURL == null) {
    it('does nor run in ci', () => {});
    return;
  }
  const tsOpStore = StaticOpStore.getInstance();
  const tsOps = tsOpStore.allOps();
  for (const opName in tsOps) {
    const tsOp = tsOps[opName];
    it(`for ${opName}`, async () => {
      const remoteOpStore = await getRemoteOpStore(remoteURL);
      const pyOp = remoteOpStore.allOps()[opName];
      if (pyOp == null) {
        throw new Error(`op ${opName} not registered in remote op store`);
      }
      const inputCompat = evaluateOpInputCompatibility(pyOp, tsOp);
      if (inputCompat.state !== CompatState.Exact) {
        throw new Error(
          `Op ${opName} inputs incompatible: ${processResult(inputCompat)}`
        );
      }
      const outputCompat = evaluateOpOutputCompatibility(pyOp, tsOp);
      if (outputCompat.state !== CompatState.Exact) {
        throw new Error(
          `Op ${opName} outputs incompatible: ${processResult(outputCompat)}`
        );
      }
    });
  }
});
