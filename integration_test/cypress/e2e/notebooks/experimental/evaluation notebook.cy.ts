import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/evaluation notebook.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/evaluation notebook.ipynb')
    );
});