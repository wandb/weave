import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/MonitorPanelPlot.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/MonitorPanelPlot.ipynb')
    );
});