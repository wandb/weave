import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/02 Tutorial - Creating ops.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/02 Tutorial - Creating ops.ipynb')
    );
});