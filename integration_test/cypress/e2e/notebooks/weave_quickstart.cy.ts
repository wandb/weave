import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/weave_quickstart.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/weave_quickstart.ipynb')
    );
});