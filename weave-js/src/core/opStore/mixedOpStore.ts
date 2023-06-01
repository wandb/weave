import {isEqual} from 'lodash';

import {outputTypeIsExecutable, outputTypeIsFunctionNode, Type} from '../model';
import {isAssignableTo} from '../model';
import {LOG_DEBUG_MESSAGES} from '../util/constants';
import {BaseOpStore} from './static';
import type {OpDef, OpStore} from './types';

/*
When loading in a python op that has the same name (id) as an existing TS op, we
have 2 sets of conditions:
1. Input Conditions:
  a. (Exact) Python inputTypes are exactly TS inputTypes
  b. (Subset) Python inputTypes are “assignable” to TS inputTypes
  c. (Superset) TS inputTypes are “assignable” to Python inputTypes
  d. (Mismatch) None of the above.
2. Output Conditions:
  a. (Unknown) Either TS or Python outputType is a function of input types
  b. (Exact) Python outputType is exactly TS outputType
  c. (Subset) Python outputType is “assignable” to TS outputType
  d. (Superset) TS outputType is “assignable” to Python outputType
  e. (Mismatch) None of the above. Now for each op in this case, we need to make
  a decision around:
    * which engine(s) are considered supported
      * The main “risk” of being conservative here is that if we “flip” an op from
        TS to just PY then it is possible existing saved panels will break since
        they will have graphs that do not have a single engine support
    * what to actually use as the input/output types during graph construction (TS
      code that builds graphs - like EE or React implementation).
      * There are two risks here:
        1. if we change any of the op def typing to use python’s flavor (assuming
          not an exact match), then our early internal users will construct
          graphs that are not executable by the TS engine - possibly resulting in
          crashes if viewed without the flag on.
        2. on the other hand, if we retain the TS op def typing, then it will be
          easier to create graphs which the system believes python can execute,
          but will result in an error since the types will be wrong to the py
          engine - crashes ONLY happen with the flag on.

Regarding #2 above, I think the desired behavior is the second option (crash at
construction time) - which we can catch during development, as opposed to in
production - and it forces us to write the python engine to conform to existing
TS types.

The logic is as follows:
  * All ops defined in TS retain ability to be executed in TS and therefore we
    never enter case #1 above
  * Do not modify existing TS type definitions (meaning we will only “fail” in
    the second way described in #2, which happens at development time, OR when
    flag is on in production)
  * Regarding which ops get flagged as supported by Py (in addition to TS): any
    op which means criteria  (1.a || 1.b) && (2.a || 2.b || 2.c).
    * This guarantees any graph constructed with the flag on is a subset of what
      the TS engine can execute and therefore cannot fail without the flag on.
      (of course, with the exception of graphs that have py-only ops)
    * The exception here is 2.a - unknown assignment due to functional returns.
      Here, I opted for the generous case and basically assume the result is
      either b/c… but we do risk having a mismatch or superset - I think this is
      a tolerable risk.
*/

// enum EnvCategory {
//   Production = 1,
//   Development,
//   CI,
// }

export enum CompatState {
  Unknown = 0,
  Exact,
  ServerIsSubset,
  ServerIsSuperset,
  Mismatch,
}

export type CompatResult = {
  state: CompatState;
  details: Array<
    | string
    | {
        key?: string;
        serverType: any;
        localType: any;
        message: string;
      }
  >;
};

const evaluateTypeCompatibility = (
  serverType: Type,
  localType: Type
): CompatState => {
  if (isAssignableTo(localType, serverType)) {
    if (isAssignableTo(serverType, localType)) {
      return CompatState.Exact;
    } else {
      return CompatState.ServerIsSuperset;
    }
  } else {
    if (isAssignableTo(serverType, localType)) {
      return CompatState.ServerIsSubset;
    } else {
      return CompatState.Mismatch;
    }
  }
};

export const compatToString = (state: CompatState) => {
  switch (state) {
    case CompatState.Exact:
      return 'Exact';
    case CompatState.ServerIsSubset:
      return 'ServerIsSubset';
    case CompatState.ServerIsSuperset:
      return 'ServerIsSuperset';
    case CompatState.Mismatch:
      return 'Mismatch';
    default:
      return 'Unknown';
  }
};

export const evaluateOpInputCompatibility = (
  serverOp: OpDef,
  localOp: OpDef
): CompatResult => {
  const serverInputKeys = Object.keys(serverOp.inputTypes);
  const localInputKeys = Object.keys(localOp.inputTypes);
  if (serverInputKeys.length !== localInputKeys.length) {
    return {
      state: CompatState.Mismatch,
      details: [
        `server has ${serverInputKeys.length} inputs, local has ${localInputKeys.length} inputs`,
      ],
    };
  }
  const numInputs = serverInputKeys.length;
  const results: CompatResult[] = [];
  for (let i = 0; i < numInputs; i++) {
    const serverInputKey = serverInputKeys[i];
    const localInputKey = localInputKeys[i];
    if (serverInputKey !== localInputKey) {
      results.push({
        state: CompatState.Mismatch,
        details: [
          `input key index ${i} on server has name ${serverInputKey}, local has name ${localInputKey}`,
        ],
      });
    }
    const compat = evaluateTypeCompatibility(
      serverOp.inputTypes[serverInputKey],
      localOp.inputTypes[localInputKey]
    );
    results.push({
      state: compat,
      details: [
        {
          key: serverInputKey,
          serverType: serverOp.inputTypes[serverInputKey],
          localType: localOp.inputTypes[localInputKey],
          message: compatToString(compat),
        },
      ],
    });
  }
  return results.reduce<CompatResult>(
    (acc, cur) => {
      let state = acc.state;
      if (acc.state === CompatState.Mismatch) {
        state = CompatState.Mismatch;
      } else if (acc.state === CompatState.Unknown) {
        if (cur.state === CompatState.Mismatch) {
          state = CompatState.Mismatch;
        }
        state = CompatState.Unknown;
      } else if (acc.state === CompatState.Exact) {
        state = cur.state;
      } else if (acc.state === CompatState.ServerIsSubset) {
        if (cur.state === CompatState.Mismatch) {
          state = CompatState.Mismatch;
        } else if (cur.state === CompatState.Unknown) {
          state = CompatState.Unknown;
        } else if (cur.state === CompatState.ServerIsSuperset) {
          state = CompatState.Mismatch;
        } else if (cur.state === CompatState.Exact) {
          state = CompatState.ServerIsSubset;
        } else if (cur.state === CompatState.ServerIsSubset) {
          state = CompatState.ServerIsSubset;
        }
      } else if (acc.state === CompatState.ServerIsSuperset) {
        if (cur.state === CompatState.Mismatch) {
          state = CompatState.Mismatch;
        } else if (cur.state === CompatState.Unknown) {
          state = CompatState.Unknown;
        } else if (cur.state === CompatState.ServerIsSuperset) {
          state = CompatState.ServerIsSuperset;
        } else if (cur.state === CompatState.Exact) {
          state = CompatState.ServerIsSubset;
        } else if (cur.state === CompatState.ServerIsSubset) {
          state = CompatState.Mismatch;
        }
      }

      return {state, details: acc.details.concat(cur.details)};
    },
    {state: CompatState.Exact, details: []}
  );
};

export const evaluateOpOutputCompatibility = (
  serverOp: OpDef,
  localOp: OpDef
): CompatResult => {
  if (outputTypeIsExecutable(localOp.outputType)) {
    return {
      state: CompatState.Unknown,
      details: [`local op has output type function`],
    };
  }
  if (outputTypeIsExecutable(serverOp.outputType)) {
    return {
      state: CompatState.Unknown,
      details: [`remote op has output type function`],
    };
  }
  if (
    outputTypeIsFunctionNode(localOp.outputType) &&
    outputTypeIsFunctionNode(serverOp.outputType)
  ) {
    if (isEqual(localOp.outputType, serverOp.outputType)) {
      return {
        state: CompatState.Exact,
        details: [],
      };
    }
    return {
      state: CompatState.Unknown,
      details: [
        {
          serverType: serverOp.outputType,
          localType: localOp.outputType,
          message: 'ops have unequal output type function nodes',
        },
      ],
    };
  } else if (outputTypeIsFunctionNode(localOp.outputType)) {
    return {
      state: CompatState.Unknown,
      details: [
        {
          serverType: serverOp.outputType,
          localType: localOp.outputType,
          message: 'localOp has function node but server op has static type',
        },
      ],
    };
  } else if (outputTypeIsFunctionNode(serverOp.outputType)) {
    return {
      state: CompatState.Unknown,
      details: [
        {
          serverType: serverOp.outputType,
          localType: localOp.outputType,
          message: 'serverOp has function node but server op has static type',
        },
      ],
    };
  }
  const compat = evaluateTypeCompatibility(
    serverOp.outputType,
    localOp.outputType
  );
  return {
    state: compat,
    details: [
      {
        serverType: serverOp.outputType,
        localType: localOp.outputType,
        message: compatToString(compat),
      },
    ],
  };
};

const shouldUsePyOp = (
  inputCompat: CompatResult,
  outputCompat: CompatResult
) => {
  return (
    (inputCompat.state === CompatState.Exact ||
      inputCompat.state === CompatState.ServerIsSubset) &&
    (outputCompat.state === CompatState.Exact ||
      outputCompat.state === CompatState.ServerIsSubset ||
      // The following condition allows for 2.a
      outputCompat.state === CompatState.Unknown)
  );
};

// Performance mixer only updates existing TS ops as Py supported
// that conform to the test described above.
export const makePerformanceMixedOpStore = (
  tsOpStore: OpStore,
  pyOpStore: OpStore
) => {
  const mixedOpStore = new BaseOpStore();
  const tsOps = tsOpStore.allOps();
  const pyOps = pyOpStore.allOps();
  for (const opName in tsOps) {
    if (tsOps[opName] == null) {
      continue;
    }
    if (opName === 'not') {
      // Makes up for the duplication hack in graph.ts
      continue;
    }
    mixedOpStore.registerOp({...tsOps[opName]});
  }
  for (const opName in pyOps) {
    if (pyOps[opName] == null) {
      continue;
    }
    const op = pyOps[opName];
    const tsOp = tsOps[opName];
    // We only use Ts- ops here
    if (tsOp != null) {
      const inputCompat = evaluateOpInputCompatibility(op, tsOp);
      const outputCompat = evaluateOpOutputCompatibility(op, tsOp);
      if (shouldUsePyOp(inputCompat, outputCompat)) {
        mixedOpStore.getOpDef(opName).supportedEngines = new Set(['ts', 'py']);
      } else {
        if (LOG_DEBUG_MESSAGES) {
          console.log(`SKIPPING UPDATE OF ${op.name} due to:`, {
            input: {
              state: compatToString(inputCompat.state),
              details: inputCompat.details,
            },
            output: {
              state: compatToString(outputCompat.state),
              details: outputCompat.details,
            },
          });
        }
      }
    }
  }
  return mixedOpStore;
};

// Ecosystem mixer marks all TS ops as Py supported
// and adds all py ops to the mix.
export const makeEcosystemMixedOpStore = (
  tsOpStore: OpStore,
  pyOpStore: OpStore
) => {
  const mixedOpStore = new BaseOpStore();
  const tsOps = tsOpStore.allOps();
  const pyOps = pyOpStore.allOps();
  for (const opName in tsOps) {
    if (tsOps[opName] == null) {
      continue;
    }
    if (opName === 'not') {
      // Makes up for the duplication hack in graph.ts
      continue;
    }
    mixedOpStore.registerOp({
      ...tsOps[opName],
      supportedEngines: new Set(['ts', 'py']),
    });
  }
  for (const opName in pyOps) {
    if (pyOps[opName] == null) {
      continue;
    }
    if (tsOps[opName] != null) {
      continue;
    }
    const op = pyOps[opName];
    mixedOpStore.registerOp({...op});
  }
  return mixedOpStore;
};
