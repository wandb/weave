import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Mnist.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Mnist.ipynb')
    );
});