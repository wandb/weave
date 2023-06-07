import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/skip_test/wandbot from scratch.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/skip_test/wandbot from scratch.ipynb')
    );
});