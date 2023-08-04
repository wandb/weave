import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/app/MonitorPanelPlot.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/app/MonitorPanelPlot.ipynb')
    );
});