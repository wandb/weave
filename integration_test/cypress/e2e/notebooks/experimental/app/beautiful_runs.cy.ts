import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/app/beautiful_runs.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/app/beautiful_runs.ipynb')
    );
});