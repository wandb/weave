import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/KerasModel.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/KerasModel.ipynb')
    );
});