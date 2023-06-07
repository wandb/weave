import {checkWeaveNotebookOutputs} from '../../e2e/notebooks/notebooks';

describe('../examples/app/WB data.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/WB data.ipynb')
    );
});