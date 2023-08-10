import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/reference/create_ops.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/create_ops.ipynb')
    );
});