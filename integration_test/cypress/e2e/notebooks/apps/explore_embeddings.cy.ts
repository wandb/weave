import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/apps/explore_embeddings.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/apps/explore_embeddings.ipynb')
    );
});