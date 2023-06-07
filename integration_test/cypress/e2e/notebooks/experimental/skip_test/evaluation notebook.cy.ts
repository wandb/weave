import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/skip_test/evaluation notebook.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/skip_test/evaluation notebook.ipynb')
    );
});