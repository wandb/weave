import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Ops that return images.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Ops that return images.ipynb')
    );
});