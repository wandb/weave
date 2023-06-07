import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/skip_test/langchain docbot.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/skip_test/langchain docbot.ipynb')
    );
});