import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Images.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Images.ipynb')
    );
});