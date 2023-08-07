import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/MonitorPanelPlot.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/MonitorPanelPlot.ipynb')
    );
});