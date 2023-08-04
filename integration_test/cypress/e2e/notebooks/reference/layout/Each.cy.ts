import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/reference/layout/Each.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/layout/Each.ipynb')
    );
});