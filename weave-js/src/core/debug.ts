//
import {StaticOpStore} from './opStore/static';
import {opDefIsLowLevel} from './runtimeHelpers';
import {DEBUG_ATTACH_TO_GLOBAL_THIS} from './util/constants';

// Useful for console debugging
if (typeof globalThis !== 'undefined' && DEBUG_ATTACH_TO_GLOBAL_THIS) {
  (globalThis as any).op = (opName: string) => {
    const opDef = StaticOpStore.getInstance().allOps()[opName];
    if (!opDef) {
      throw new TypeError(`unknown op: '${opName}'`);
    }
    return (...args: any[]) => {
      // Map pos args to input object keys by definition order
      const argObj = Object.keys(opDef.inputTypes).reduce((obj, key, index) => {
        let posArg = args[index];

        if (typeof posArg === 'undefined') {
          throw new TypeError(`missing value for input '${key}'`);
        } else if (typeof posArg !== 'object') {
          // Naively wrap js non-object primitives as const node
          posArg = {
            nodeType: 'const',
            type: typeof posArg,
            val: posArg,
          };
        }

        (obj as any)[key] = posArg;
        return obj;
      }, {});
      if (opDefIsLowLevel(opDef)) {
        return opDef.op(argObj as any);
      }
      return null;
    };
  };
}
