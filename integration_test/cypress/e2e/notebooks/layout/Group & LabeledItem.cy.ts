import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/layout/Group & LabeledItem.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/layout/Group & LabeledItem.ipynb')
    );
});