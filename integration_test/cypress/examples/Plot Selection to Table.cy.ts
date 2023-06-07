import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Plot Selection to Table.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Plot Selection to Table.ipynb')
    );
});