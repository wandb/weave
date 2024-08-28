import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../weave/legacy/examples/experimental/app/RunChain.ipynb notebook test', () => {
  // Skipping until this is stable
  it.skip('passes', () => {
    return checkWeaveNotebookOutputs(
      '../weave/legacy/examples/experimental/app/RunChain.ipynb'
    );
  });
});
