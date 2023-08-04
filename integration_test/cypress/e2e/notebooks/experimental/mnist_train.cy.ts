import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/mnist_train.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/mnist_train.ipynb')
    );
});