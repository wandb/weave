import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/Embeddings.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/Embeddings.ipynb')
    );
});