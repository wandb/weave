import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/bert_viz.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/bert_viz.ipynb')
    );
});