import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../weave/legacy/examples/experimental/MonitorPanelPlot.ipynb notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs(
      '../weave/legacy/examples/experimental/MonitorPanelPlot.ipynb'
    ));
});
