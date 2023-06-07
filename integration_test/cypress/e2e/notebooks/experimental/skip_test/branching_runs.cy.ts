import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/skip_test/branching_runs.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/skip_test/branching_runs.ipynb')
    );
});