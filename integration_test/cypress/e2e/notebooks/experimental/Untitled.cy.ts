import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Untitled.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Untitled.ipynb')
    );
});