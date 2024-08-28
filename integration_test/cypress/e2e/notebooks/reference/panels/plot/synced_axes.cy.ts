import {checkWeaveNotebookOutputs} from '../../../notebooks';

describe('../weave/legacy/examples/reference/panels/plot/synced_axes.ipynb notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs(
      '../weave/legacy/examples/reference/panels/plot/synced_axes.ipynb'
    ));
});
