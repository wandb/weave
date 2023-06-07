import {checkWeaveNotebookOutputs} from '../../e2e/notebooks/notebooks';

describe('../examples/app/art_explore.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/art_explore.ipynb')
    );
});