import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/wandbot from scratch.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/wandbot from scratch.ipynb')
    );
});