import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Mutations.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Mutations.ipynb')
    );
});