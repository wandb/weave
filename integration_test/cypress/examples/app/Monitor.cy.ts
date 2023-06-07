import {checkWeaveNotebookOutputs} from '../../e2e/notebooks/notebooks';

describe('../examples/app/Monitor.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/Monitor.ipynb')
    );
});