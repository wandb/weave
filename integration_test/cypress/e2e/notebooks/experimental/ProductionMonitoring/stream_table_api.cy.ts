import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/ProductionMonitoring/stream_table_api.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/ProductionMonitoring/stream_table_api.ipynb')
    );
});