import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Mutations.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Mutations.ipynb')
    );
});