import {checkWeaveNotebookOutputs} from '../../e2e/notebooks/notebooks';

describe('../examples/experimental/Vectorizing.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Vectorizing.ipynb')
    );
});