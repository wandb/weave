import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/beautiful_runs.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/beautiful_runs.ipynb')
    );
});