import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Inference logs example.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Inference logs example.ipynb')
    );
});