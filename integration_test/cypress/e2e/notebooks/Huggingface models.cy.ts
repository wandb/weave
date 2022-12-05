import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Huggingface models.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Huggingface models.ipynb')
    );
});