import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/tutorial/huggingface_datasets.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/tutorial/huggingface_datasets.ipynb')
    );
});