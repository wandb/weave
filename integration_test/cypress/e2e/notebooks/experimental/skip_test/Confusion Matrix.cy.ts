import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/skip_test/Confusion Matrix.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/skip_test/Confusion Matrix.ipynb')
    );
});