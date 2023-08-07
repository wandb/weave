import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/reference/layout/Group & LabeledItem.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/layout/Group & LabeledItem.ipynb')
    );
});