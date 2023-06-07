import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/skip_test/00 Tutorial - Data versioning.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/skip_test/00 Tutorial - Data versioning.ipynb')
    );
});