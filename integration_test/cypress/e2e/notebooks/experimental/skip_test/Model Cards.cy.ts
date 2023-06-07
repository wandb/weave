import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/skip_test/Model Cards.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/skip_test/Model Cards.ipynb')
    );
});