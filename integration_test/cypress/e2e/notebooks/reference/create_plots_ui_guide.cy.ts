import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../weave/legacy/examples/reference/create_plots_ui_guide.ipynb notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs(
      '../weave/legacy/examples/reference/create_plots_ui_guide.ipynb'
    ));
});
