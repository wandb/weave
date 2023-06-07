import {checkWeaveNotebookOutputs} from '../../e2e/notebooks/notebooks';

describe('../examples/experimental/Custom ops.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Custom ops.ipynb')
    );
});