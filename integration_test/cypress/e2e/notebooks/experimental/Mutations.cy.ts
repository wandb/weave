import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../weave/legacy/examples/experimental/Mutations.ipynb notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs(
      '../weave/legacy/examples/experimental/Mutations.ipynb'
    ));
});
