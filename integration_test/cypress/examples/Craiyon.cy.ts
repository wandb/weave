import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Craiyon.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Craiyon.ipynb')
    );
});