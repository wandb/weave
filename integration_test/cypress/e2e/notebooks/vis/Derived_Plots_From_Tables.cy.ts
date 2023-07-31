import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/vis/derived_plots_from_tables.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/vis/derived_plots_from_tables.ipynb')
    );
});