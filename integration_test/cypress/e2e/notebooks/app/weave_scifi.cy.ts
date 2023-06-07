import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/weave_scifi.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/weave_scifi.ipynb')
    );
});