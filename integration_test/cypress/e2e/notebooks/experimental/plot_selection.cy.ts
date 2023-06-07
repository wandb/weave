import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/plot_selection.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/plot_selection.ipynb')
    );
});