import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../weave/legacy/examples/experimental/app/scenario_compare.ipynb notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs(
      '../weave/legacy/examples/experimental/app/scenario_compare.ipynb'
    ));
});
