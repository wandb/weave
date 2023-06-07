import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/vis/TimeSeries.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/vis/TimeSeries.ipynb')
    );
});