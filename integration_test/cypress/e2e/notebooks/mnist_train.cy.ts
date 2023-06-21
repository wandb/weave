import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/mnist_train.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/mnist_train.ipynb')
    );
});