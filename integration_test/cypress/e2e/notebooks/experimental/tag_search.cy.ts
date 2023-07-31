import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/tag_search.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/tag_search.ipynb')
    );
});