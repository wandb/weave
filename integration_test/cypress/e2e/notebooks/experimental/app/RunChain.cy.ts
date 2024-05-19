import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/app/RunChain.ipynb notebook test', () => {
  // Skipping until this is stable
  it.skip('passes', () => {
    return checkWeaveNotebookOutputs(
      '../examples/experimental/app/RunChain.ipynb'
    );
  });
});
