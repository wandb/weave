import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/reference/create_plots_ui_guide.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/create_plots_ui_guide.ipynb')
    );
});