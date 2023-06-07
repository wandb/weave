import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Mutation.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Mutation.ipynb')
    );
});