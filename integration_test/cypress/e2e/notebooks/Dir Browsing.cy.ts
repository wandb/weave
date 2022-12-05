import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Dir Browsing.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Dir Browsing.ipynb')
    );
});