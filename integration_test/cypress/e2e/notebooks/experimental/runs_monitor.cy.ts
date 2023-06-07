import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/runs_monitor.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/runs_monitor.ipynb')
    );
});