import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/skip_test/04 Tutorial - Publishing Data and Ops.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/skip_test/04 Tutorial - Publishing Data and Ops.ipynb')
    );
});