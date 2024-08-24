import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../weave/legacy/examples/reference/confusion_matrix.ipynb notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs(
      '../weave/legacy/examples/reference/confusion_matrix.ipynb'
    ));
});
