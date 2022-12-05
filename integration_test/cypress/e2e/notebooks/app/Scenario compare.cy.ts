import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/Scenario compare.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/Scenario compare.ipynb')
    );
});