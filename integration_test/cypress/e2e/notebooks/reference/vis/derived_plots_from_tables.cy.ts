import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/reference/vis/derived_plots_from_tables.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/vis/derived_plots_from_tables.ipynb')
    );
});