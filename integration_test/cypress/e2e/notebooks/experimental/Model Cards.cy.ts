import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Model Cards.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Model Cards.ipynb')
    );
});