import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../weave/legacy/examples/reference/vis/Distribution.ipynb notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs(
      '../weave/legacy/examples/reference/vis/Distribution.ipynb'
    ));
});
