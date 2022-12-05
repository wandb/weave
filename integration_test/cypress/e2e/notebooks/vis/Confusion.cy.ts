import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/vis/Confusion.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/vis/Confusion.ipynb')
    );
});