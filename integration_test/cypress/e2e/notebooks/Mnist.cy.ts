import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/mnist.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/mnist.ipynb')
    );
});