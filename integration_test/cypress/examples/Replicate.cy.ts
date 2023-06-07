import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Replicate.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Replicate.ipynb')
    );
});