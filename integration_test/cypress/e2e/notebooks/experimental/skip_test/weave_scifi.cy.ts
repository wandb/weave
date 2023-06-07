import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/skip_test/weave_scifi.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/skip_test/weave_scifi.ipynb')
    );
});