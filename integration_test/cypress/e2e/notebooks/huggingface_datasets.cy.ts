import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/huggingface_datasets.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/huggingface_datasets.ipynb')
    );
});