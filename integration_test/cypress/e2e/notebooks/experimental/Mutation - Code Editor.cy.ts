import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Mutation - Code Editor.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Mutation - Code Editor.ipynb')
    );
});