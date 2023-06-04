import {OpDef} from '@wandb/weave/core';

// In Weave expression language, certain op styles receive their first
// input from the LHS of the expression, instead of as an input parameter
export function shouldSkipOpFirstInput(opDef: OpDef): boolean {
  return ['chain', 'brackets', 'binary'].includes(opDef.renderInfo.type);
}

// const SHOW_DEBUG_LOG = false;
const SHOW_DEBUG_LOG = true;

export const consoleLog = (...msg: any[]) => {
  if (SHOW_DEBUG_LOG) {
    console.log(...msg);
  }
};

export const consoleGroup = (...msg: any[]) => {
  if (SHOW_DEBUG_LOG) {
    console.group(...msg);
  }
};

export const consoleWarn = (...msg: any[]) => {
  if (SHOW_DEBUG_LOG) {
    console.warn(...msg);
  }
};
