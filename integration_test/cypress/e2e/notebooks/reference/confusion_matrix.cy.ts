import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/reference/confusion_matrix.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/confusion_matrix.ipynb')
    );
});