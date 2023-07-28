import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/MonitorPanelPlotGeneric.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/MonitorPanelPlotGeneric.ipynb')
    );
});