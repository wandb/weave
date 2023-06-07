import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Confusion Matrix.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Confusion Matrix.ipynb')
    );
});