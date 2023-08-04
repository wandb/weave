import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/tutorial/composite_histograms.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/tutorial/composite_histograms.ipynb')
    );
});