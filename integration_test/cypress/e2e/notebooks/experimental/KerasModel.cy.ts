import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/KerasModel.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/KerasModel.ipynb')
    );
});