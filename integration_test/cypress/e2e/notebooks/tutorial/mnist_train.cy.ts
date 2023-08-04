import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/tutorial/mnist_train.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/tutorial/mnist_train.ipynb')
    );
});