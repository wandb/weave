import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Mutations.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Mutations.ipynb')
    );
});