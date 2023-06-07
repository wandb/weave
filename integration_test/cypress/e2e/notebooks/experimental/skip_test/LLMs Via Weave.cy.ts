import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/skip_test/LLMs Via Weave.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/skip_test/LLMs Via Weave.ipynb')
    );
});