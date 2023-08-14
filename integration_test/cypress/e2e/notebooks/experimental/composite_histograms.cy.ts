import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/composite_histograms.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/composite_histograms.ipynb')
    );
});