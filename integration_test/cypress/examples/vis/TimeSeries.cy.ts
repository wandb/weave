import {checkWeaveNotebookOutputs} from '../../e2e/notebooks/notebooks';

describe('../examples/vis/TimeSeries.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/vis/TimeSeries.ipynb')
    );
});