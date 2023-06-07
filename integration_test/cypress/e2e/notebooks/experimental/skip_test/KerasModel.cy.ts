import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/skip_test/KerasModel.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/skip_test/KerasModel.ipynb')
    );
});