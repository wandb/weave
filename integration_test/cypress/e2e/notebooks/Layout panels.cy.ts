import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Layout panels.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Layout panels.ipynb')
    );
});