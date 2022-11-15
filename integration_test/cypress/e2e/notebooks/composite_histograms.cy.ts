import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/composite_histograms.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/composite_histograms.ipynb')
    );
});