import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/tutorial/weave_walkthrough.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/tutorial/weave_walkthrough.ipynb')
    );
});