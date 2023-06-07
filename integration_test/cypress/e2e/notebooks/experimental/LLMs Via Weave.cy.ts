import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/LLMs Via Weave.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/LLMs Via Weave.ipynb')
    );
});