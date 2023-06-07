import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Branching Runs.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Branching Runs.ipynb')
    );
});