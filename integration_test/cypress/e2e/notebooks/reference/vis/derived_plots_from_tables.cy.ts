import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../weave/legacy/examples/reference/vis/derived_plots_from_tables.ipynb notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs(
      '../weave/legacy/examples/reference/vis/derived_plots_from_tables.ipynb'
    ));
});
