import {checkWeaveNotebookOutputs} from '../../e2e/notebooks/notebooks';

describe('../examples/layout/Each.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/layout/Each.ipynb')
    );
});