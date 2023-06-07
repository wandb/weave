import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/OpenAI.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/OpenAI.ipynb')
    );
});