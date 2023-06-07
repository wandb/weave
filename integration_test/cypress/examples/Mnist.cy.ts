import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Mnist.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Mnist.ipynb')
    );
});