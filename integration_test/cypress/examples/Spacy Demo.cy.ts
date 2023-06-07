import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Spacy Demo.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Spacy Demo.ipynb')
    );
});