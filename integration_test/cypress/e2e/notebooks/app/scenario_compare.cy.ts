import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/scenario_compare.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/scenario_compare.ipynb')
    );
});