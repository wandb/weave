import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Huggingface datasets.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Huggingface datasets.ipynb')
    );
});