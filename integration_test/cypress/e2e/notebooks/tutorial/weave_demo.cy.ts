import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/tutorial/weave_demo.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/tutorial/weave_demo.ipynb')
    );
});