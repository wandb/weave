import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/spacy_demo.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/spacy_demo.ipynb')
    );
});