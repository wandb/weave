import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/app/scenario_compare.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/app/scenario_compare.ipynb')
    );
});