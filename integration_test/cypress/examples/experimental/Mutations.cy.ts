import {checkWeaveNotebookOutputs} from '../../e2e/notebooks/notebooks';

describe('../examples/experimental/Mutations.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Mutations.ipynb')
    );
});