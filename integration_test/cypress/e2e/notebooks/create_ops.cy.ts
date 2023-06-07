import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/create_ops.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/create_ops.ipynb')
    );
});