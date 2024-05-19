import {Closure, Definition, Frame, Stack} from './types';

export const emptyStack = (): Stack => [];

export const pushFrameDefs = <D extends Definition>(
  stack: D[],
  frame: D[]
): D[] => {
  const res = [...stack];
  for (const def of frame) {
    res.splice(0, 0, def);
  }
  return res;
};

export const pushFrame = (
  stack: Stack,
  frame: Frame,
  extra?: {[key: string]: any}
): Stack => {
  const res = [...stack];
  for (const [name, value] of Object.entries(frame ?? {})) {
    if (value == null) {
      throw new Error('encountered null value! Programming error');
    }
    res.splice(0, 0, {name, value, ...extra});
  }
  return res;
};

export const toFrame = (stack: Stack): Frame => {
  const reversedStack = [...stack];
  reversedStack.reverse();
  const res: Frame = {};
  for (const {name, value} of reversedStack) {
    res[name] = value;
  }
  return res;
};

// Weave variable resolution.
//
// Variables cannot reference themselves (no recursive references).
// So we find the first definition of the variable, and return it
// along with the stack above that point.
export const resolveVar = <D extends Definition>(
  stack: D[],
  varName: string
): {closure: Closure; entry: D} | null => {
  const defIndex = stack.findIndex(d => d.name === varName);
  if (defIndex === -1) {
    return null;
  }
  return {
    closure: {
      stack: stack.slice(defIndex + 1),
      value: stack[defIndex].value,
    },
    entry: stack[defIndex],
  };
};
