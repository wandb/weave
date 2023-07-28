import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/ProductionMonitoring/ProductionMonitoringConceptualOverview.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/ProductionMonitoring/ProductionMonitoringConceptualOverview.ipynb')
    );
});