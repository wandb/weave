import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/skip_test/WB data.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/skip_test/WB data.ipynb')
    );
});