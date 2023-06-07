import {checkWeaveNotebookOutputs} from '../../e2e/notebooks/notebooks';

describe('../examples/vis/Confusion.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/vis/Confusion.ipynb')
    );
});