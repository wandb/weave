import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../weave/legacy/examples/reference/vis/Scatter.ipynb notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs(
      '../weave/legacy/examples/reference/vis/Scatter.ipynb'
    ));
});
