import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/vis/Derived_Plots_From_Tables.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/vis/Derived_Plots_From_Tables.ipynb')
    );
});