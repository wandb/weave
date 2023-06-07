import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Oxford-IIIT Pet Dataset.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Oxford-IIIT Pet Dataset.ipynb')
    );
});