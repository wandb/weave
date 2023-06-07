import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/bert_viz.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/bert_viz.ipynb')
    );
});