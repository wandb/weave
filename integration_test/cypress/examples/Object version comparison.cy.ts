import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Object version comparison.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Object version comparison.ipynb')
    );
});