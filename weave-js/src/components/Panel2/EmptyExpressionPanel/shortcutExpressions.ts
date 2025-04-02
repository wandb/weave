import {Node, opRunConfig, opRunHistory, opRunSummary} from '@wandb/weave/core';

export const runSummary = (runNode: Node) => {
  return opRunSummary({run: runNode});
};

export const runHistory = (runNode: Node) => {
  return opRunHistory({run: runNode});
};

export const runConfig = (runNode: Node) => {
  return opRunConfig({run: runNode});
};
