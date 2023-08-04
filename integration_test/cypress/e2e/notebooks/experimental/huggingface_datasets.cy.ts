import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/huggingface_datasets.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/huggingface_datasets.ipynb')
    );
});