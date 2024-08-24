import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../weave/legacy/examples/reference/layout/Each.ipynb notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs(
      '../weave/legacy/examples/reference/layout/Each.ipynb'
    ));
});
