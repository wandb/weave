import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/skip_test/Weave geo data.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/skip_test/Weave geo data.ipynb')
    );
});