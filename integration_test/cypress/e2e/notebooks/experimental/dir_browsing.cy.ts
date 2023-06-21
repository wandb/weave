import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/dir_browsing.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/dir_browsing.ipynb')
    );
});