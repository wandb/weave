import {checkWeaveNotebookOutputs} from '../../e2e/notebooks/notebooks';

describe('../examples/vis/Scatter.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/vis/Scatter.ipynb')
    );
});