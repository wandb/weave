import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/ecosystem.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/ecosystem.ipynb')
    );
});