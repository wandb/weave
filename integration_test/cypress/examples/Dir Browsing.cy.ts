import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Dir Browsing.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Dir Browsing.ipynb')
    );
});